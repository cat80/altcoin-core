"""
blockchain.py
这是核心的区块链管理类。
它作为总指挥，协调 block_storage, block_index, chain_state, 和 block_validator
等组件，共同处理新区块的接收、验证、存储和链重组。
"""
import logging
import os
import time
from pickle import FRAME
from typing import Optional, List, Tuple

from config import INITIAL_BLOCK_REWARD
from .block import Block, BlockHeader
from .transaction import Transaction, TxIn, TxOut
from .block_index import BlockIndex
from .chain_state import ChainState,ChainStateCacheView
from .block_validator import BlockValidator
from .block_storage import BlockStorage
from config import *

log = logging.getLogger(__name__)

class Blockchain:
    """
    顶层的区块链管理类。
    """
    block_storage :BlockStorage
    block_index :BlockIndex
    chain_state:ChainState

    @classmethod
    def new_from_data_dir(cls,data_dir:str):
        """
            根据数据路径自动初始化相关对象，该方法主要用来创建单元测试对象。生产环境请调用构造方法注入需要状态管理的对象。
        :param data_dir:
        :return:
        """
        from storage import SQLAlchemyWrapper,RocksDBWrapper
        os.makedirs(data_dir,exist_ok=True)
        sqldb = SQLAlchemyWrapper(os.path.join(data_dir,'index.db'))
        sqldb.create_all_tables()
        rocks_db = RocksDBWrapper(os.path.join(data_dir,'utxo'))
        chainState = ChainState(rocks_db)
        blockStorage = BlockStorage(os.path.join(data_dir,'block'))
        blockIndex = BlockIndex(sqldb=sqldb)
        return cls(
            block_index=blockIndex,
            block_storage=blockStorage,
            chain_state=chainState
        )
    def __init__(self,block_storage :BlockStorage,block_index :BlockIndex,chain_state:ChainState):
        """
            初始化状态。使用依赖注入，block本身不创建需要依赖外部的对象
        :param block_storage:
        :param block_index:
        :param chain_state:
        """
        self.block_storage =block_storage
        self.block_index = block_index
        self.chain_state = chain_state
        # 加载或创建创世区块
        self._init_genesis_block()

    def _init_genesis_block(self):
        """
        如果区块链为空，则创建并存储创世区块。
        """
        if self.block_index.get_tip() is None:
            # 创世区块定义
            genesis_header = BlockHeader(1, b'\x00'*32, bytes.fromhex("4a5e1e4baab89f3a32518a88c31bc87f618f76673e2cc77ab2127b7afdeda33b"), int(time.time()), 0x1e097dea, 2083236893)
            coinbase_tx = Transaction(1, [TxIn.create_coinbase_txin(b'30/Sep/2025. Failed to HODL the last cycle, I realized the only way to win was to code my own coin.')], [TxOut(INITIAL_BLOCK_REWARD, b'1CjFwRdfSTjbzENgrvstqSfXX1vHRe4RVM')], 0)
            genesis_block = Block(genesis_header, [coinbase_tx])

            # 验证并存储创世区块
            file_index, offset = self.block_storage.write_block(genesis_block)
            # 初始工作量计算
            work = 2**256 / (BlockValidator.bits_to_target(genesis_block.header.bits) + 1)
            self.block_index.add_header(genesis_block.header, 0, work, file_index, offset,BLOCK_STATUS_VALID)
            self.chain_state.apply_block(genesis_block)
            log.info("Genesis block created and initialized.")

    def add_block(self, block: Block) -> bool:
        """
        核心业务逻辑: 尝试将一个新区块添加到区块链中。
        这包括验证、存储、更新索引和状态，以及处理可能的分叉和重组。
        """
        block_hash = block.hash()

        log.debug(f'start handle add block,block hash:{block.hash().hex()},trans count:{len(block.transactions)},coinbase hashid:{block.transactions[0].hash().hex()}')
        # 1. 初步验证 (无状态，快速失败)，这里主要验证pow是否有效
        if not BlockValidator.check_block_header(block.header):
            log.debug(f"Block {block_hash.hex()} failed header validation (PoW).")
            return False
         # 2. 检查父区块是否存在于索引中
        prev_hash = block.header.prev_block_hash
        prev_header_info = self.block_index.get_header_info(prev_hash)
        
        if prev_header_info is None:
            # 暂时不处理孤立节点的问题，这里返回多个状态，让上一级事件处理方法处理
            log.info(f"Block {block_hash.hex()} is an orphan block, parent {prev_hash.hex()} not found.")
            return False    # 3. 计算新区块的高度和工作量

        new_height = prev_header_info['height'] + 1
        work = 2**256 / (BlockValidator.bits_to_target(block.header.bits) + 1)
        new_total_work = prev_header_info['total_work'] + work

        # 这里继续检查bits的有效性，确保非法pow bits不被区块接受
        required_bits = self.block_index.calculate_required_bits(new_height,prev_header_info)
        if required_bits != block.header.bits:
            log.info(f'block:{block.header.hash().hex()} bit not satisfied required.except bits :{required_bits},actual bits:{block.header.bits}')
            return False
        # 到这里已经说明区块的pow,bits是符合规则的并且也不是孤立区块，开始考虑处理分叉的问题。
        current_tip = self.block_index.get_tip()

        # 如果区块父级元素也是当前主链的顶端
        if current_tip['block_hash'] == block.header.prev_block_hash:
            # 验证utxo有效后，直接存储数据并更新chain state
            if not BlockValidator.check_block(block, self.chain_state, self.block_index, prev_header_info):
                log.info(f"Block {block_hash.hex()} failed full validation.")
                # 注意：如果区块本身无效保存数据库没有意义直接丢掉
                return False
            # 写入文件，增加utxo索引，更新utxo状态。这里应该是一个事务，具有原子性，这里暂时不做处理，在父级插入成功的时候，做一个简单的验证，确保最顶端的coinbase在utxo中有效即可。
            file_index, offset = self.block_storage.write_block(block)
            self.block_index.add_header(block.header, new_height, new_total_work, file_index, offset,BLOCK_STATUS_VALID)
            self.chain_state.apply_block(block)
            return True
        else:
            # 这里处理分叉和重组，只要prev_hash在区块中存在，则直接持久化数据，但不更新utxo状态.标记block index为分支侧 链
            file_index, offset = self.block_storage.write_block(block)
            self.block_index.add_header(block.header, new_height, new_total_work, file_index, offset,
                                        BLOCK_STATUS_INVALID)
            # 这里处理的是侧链分叉和重组的问题
            # 处理对决，如果侧链为总工作量大于当前

            if new_total_work > current_tip['total_work'] or new_height>current_tip['height']:
                # 如果侧链的工作 量比当前的主链更大则进行重组
                return self._handle_reorganization(block,current_tip)
            else:
               #  成功增加到侧链
               return True


    def _handle_reorganization(self, new_chain_tip_block: Block, old_tip_info: dict) -> bool:
        """
        处理链重组的完整逻辑。
        1. 找到共同祖先。
        2. 在缓存视图中回滚旧链区块，同时构建数据库批处理。
        3. 在缓存视图中应用新链区块，同时验证并构建数据库批处理。
        4. 如果全部验证成功，则原子性地提交数据库批处理，并更新区块索引状态。
        """
        log.info(f"Reorganization triggered by new block {new_chain_tip_block.hash().hex()}. Old tip: {old_tip_info['block_hash'].hex()}")
        
        new_tip_info = self.block_index.get_header_info(new_chain_tip_block.hash())
        if not new_tip_info:
            log.error("Could not find header info for the new chain tip during reorganization.")
            return False

        ancestor_hash, old_blocks_info, new_blocks_info = self.block_index.find_common_ancestor(
            new_tip_info['block_hash'], old_tip_info['block_hash']
        )

        if not ancestor_hash:
            log.error("Reorganization failed: Could not find a common ancestor.")
            return False

        log.info(f"Common ancestor: {ancestor_hash.hex()}. Rolling back {len(old_blocks_info)} blocks, applying {len(new_blocks_info)} blocks.")

        cache_view = ChainStateCacheView(self.chain_state)
        
        # 1. 模拟回滚旧链区块
        for block_info in old_blocks_info:
            block = self.block_storage.read_block(block_info['file_index'], block_info['file_offset'])
            if not block:
                log.error(f"Failed to read block {block_info['block_hash'].hex()} from storage for rollback.")
                return False
            
            # 为了回滚，需要找到这个区块花掉的UTXO
            spent_utxos = self._find_spent_utxos_for_block(block)
            cache_view.revert_block(block, spent_utxos)

        # 2. 模拟并验证应用新链区块
        for block_info in new_blocks_info:
            block = self.block_storage.read_block(block_info['file_index'], block_info['file_offset'])
            if not block:
                log.error(f"Failed to read block {block_info['block_hash'].hex()} from storage for applying.")
                return False
            
            prev_hash = block.header.prev_block_hash
            # 在验证时，我们需要前一个区块的信息，这可能在旧链、新链或缓存视图中
            prev_header_info = self.block_index.get_header_info(prev_hash)

            # 使用缓存视图进行验证
            if not BlockValidator.check_block(block, cache_view, self.block_index, prev_header_info):
                log.warning(f"Reorganization failed: New chain block {block.hash().hex()} failed validation.")
                return False
            
            # 验证通过，将变更应用到缓存视图
            cache_view.apply_block(block)

        # 3. 所有验证通过，提交变更
        # a. 提交UTXO变更
        final_batch = cache_view.get_batch()

        log.debug(f'reorg batch write len:{final_batch.len()}')
        self.chain_state.commit_utxo_batch(final_batch)
        
        # b. 更新区块索引状态
        old_hashes = [b['block_hash'] for b in old_blocks_info]
        new_hashes = [b['block_hash'] for b in new_blocks_info]
        self.block_index.update_blocks_status(old_hashes, BLOCK_STATUS_INVALID)
        self.block_index.update_blocks_status(new_hashes, BLOCK_STATUS_VALID)

        log.info(f"Reorganization successful. New tip is now {new_tip_info['block_hash'].hex()}.")
        return True

    def _find_spent_utxos_for_block(self, block: Block) -> List[Tuple[TxIn, TxOut]]:
        """
        辅助函数：为给定的区块找到所有被其花费的UTXO。
        这在回滚时是必需的。
        """
        spent_utxos = []
        for tx in block.transactions:
            if not tx.is_coinbase():
                for tx_in in tx.tx_ins:
                    # 在当前状态下查找UTXO，因为此时尚未回滚
                    utxo = self.chain_state.get_utxo(tx_in)
                    if utxo:
                        spent_utxos.append((tx_in, utxo))
        return spent_utxos

    def get_best_tip(self) -> Optional[dict]:
        """返回主链顶端的信息。"""
        return self.block_index.get_tip()

    def close(self):
        self.block_index.close()
        self.chain_state.close()
