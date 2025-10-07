"""
blockchain.py
这是核心的区块链管理类。
它作为总指挥，协调 block_storage, block_index, chain_state, 和 block_validator
等组件，共同处理新区块的接收、验证、存储和链重组。
"""
import os
import time
from typing import Optional, List, Tuple

from .block import Block, BlockHeader
from .transaction import Transaction, TxIn, TxOut
from .block_index import BlockIndex
from .chain_state import ChainState
from .block_validator import BlockValidator
from .block_storage import BlockStorage
from utils import log

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
            coinbase_tx = Transaction(1, [TxIn.create_coinbase_txin(b'30/Sep/2025. Failed to HODL the last cycle, I realized the only way to win was to code my own coin.')], [TxOut(50*100000000, b'1CjFwRdfSTjbzENgrvstqSfXX1vHRe4RVM')], 0)
            genesis_block = Block(genesis_header, [coinbase_tx])

            # 验证并存储创世区块
            file_index, offset = self.block_storage.write_block(genesis_block)
            # 初始工作量计算
            work = 2**256 / (BlockValidator.bits_to_target(genesis_block.header.bits) + 1)
            self.block_index.add_header(genesis_block.header, 0, work, file_index, offset)
            self.chain_state.apply_block(genesis_block)
            print("Genesis block created and initialized.")

    def add_block(self, block: Block) -> bool:
        """
        核心业务逻辑: 尝试将一个新区块添加到区块链中。
        这包括验证、存储、更新索引和状态，以及处理可能的分叉和重组。
        """
        block_hash = block.hash()
        
        # 1. 初步验证 (无状态，快速失败)
        if not BlockValidator.check_block_header(block.header):
            log.debug(f"Block {block_hash.hex()} failed header validation (PoW).")
            return False
            
        # 2. 检查父区块是否存在于索引中
        prev_hash = block.header.prev_block_hash
        prev_header_info = self.block_index.get_header_info(prev_hash)
        
        if prev_header_info is None:
            # 暂时不处理孤立节点的问题
            print(f"Block {block_hash.hex()} is an orphan block, parent {prev_hash.hex()} not found.")
            return False

        # 3. 存储完整区块到磁盘 (在完整验证前，先存盘)
        file_index, offset = self.block_storage.write_block(block)
        
        # 4. 计算新区块的高度和工作量
        new_height = prev_header_info['height'] + 1
        work = 2**256 / (BlockValidator.bits_to_target(block.header.bits) + 1)
        new_total_work = prev_header_info['total_work'] + work

        # 5. 添加区块头到索引
        self.block_index.add_header(block.header, new_height, new_total_work, file_index, offset)

        # 6. 检查是否需要链重组
        current_tip = self.block_index.get_tip()
        if current_tip['block_hash'] != block_hash:
            # 新区块的总工作量更大，需要重组
            print(f"Reorganization needed. New tip: {block_hash.hex()}")
            return self._handle_reorganization(prev_header_info, block)

        # 7. 如果是在主链上延长，进行完整验证并更新状态
        if not BlockValidator.check_block(block, self.chain_state, self.block_index, prev_header_info):
            print(f"Block {block_hash.hex()} failed full validation.")
            # 注意：此时区块头已存入索引，需要一个机制将其标记为无效
            return False
            
        self.chain_state.apply_block(block)
        
        print(f"Successfully added block {block_hash.hex()} at height {new_height}.")
        return True

    def _handle_reorganization(self, new_chain_tip_info: dict, new_block: Block) -> bool:
        """处理链重组的复杂逻辑。"""
        # 这是一个复杂的过程，这里提供一个简化的逻辑框架
        # 1. 找到共同祖先
        # 2. 回滚旧链的区块
        # 3. 应用新链的区块
        print("Chain reorganization is a complex feature and is not fully implemented in this scaffold.")
        # 简化处理：直接切换状态（这在真实场景中是不安全的）
        # 真实的实现需要一个循环来回滚和应用
        
        # 警告：以下为非原子性、不完整的示例，仅为演示流程
        # old_tip = self.get_best_tip() # 需要找到分叉前的tip
        # self.chain_state.revert_block(...)
        # self.chain_state.apply_block(...)
        return True

    def get_best_tip(self) -> Optional[dict]:
        """返回主链顶端的信息。"""
        return self.block_index.get_tip()

    def close(self):
        self.block_index.close()
        self.chain_state.close()
