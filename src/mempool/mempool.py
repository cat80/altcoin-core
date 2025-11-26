from p2p.event_bus import EventBus
from core import Blockchain, BlockValidator, Block, Transaction
import logging
log = logging.getLogger(__name__)

class Mempool:
    """
    交易内存池。
    核心职责：只管理未被打包进区块的有效交易。
    """
    def __init__(self, event_bus: EventBus, blockchain: Blockchain):
        self.event_bus = event_bus
        self.blockchain = blockchain

        # 未打包的交易: {tx_hash: Transaction}
        self.transactions = {}
        # 用于防止双花的集合，存储已被mempool中交易花费的UTXO引用 (tx_hash:index)
        self.spent_utxos = set()

        # 订阅区块确认事件，以便清理已打包的交易
        self.event_bus.subscribe('block_validated', self.on_block_validated)
        # 收到新的区块
        self.event_bus.subscribe("recv_new_tx", self.add_transaction)

    def get_local_pack_transactions(self):
        """
        获取可打包的交易列表，并进行最终的双花检查。
        """
        pack_txs = []
        remove_keys = []
        
        # 打包前的最终双花检查
        seen_utxos_for_packing = set()
        for tx in self.transactions.values():
            tx_hash = tx.hash()
            # 检查交易是否仍然有效
            if not BlockValidator.check_tx(tx, self.blockchain.chain_state):
                log.warning(f"Transaction {tx_hash.hex()} is no longer valid. Removing from mempool.")
                remove_keys.append(tx_hash)
                continue

            # 检查这笔交易的输入是否与已选入打包列表的其他交易冲突
            has_conflict = False
            tx_inputs = set()
            for tx_in in tx.tx_ins:
                utxo_ref = f"{tx_in.prev_tx_hash.hex()}:{tx_in.prev_tx_out_index}"
                if utxo_ref in seen_utxos_for_packing:
                    has_conflict = True
                    break
                tx_inputs.add(utxo_ref)
            
            if has_conflict:
                log.warning(f"Transaction {tx_hash.hex()} conflicts with others in packing list. Skipping for this block.")
                continue

            pack_txs.append(tx)
            seen_utxos_for_packing.update(tx_inputs)

        # 清理在检查过程中发现的无效交易
        for key in remove_keys:
            self.remove_transaction(key)
            
        return pack_txs

    def calculate_fee(self, tx: Transaction) -> int:
        """辅助函数：计算交易费用"""
        if tx.is_coinbase():
            return 0
        try:
            input_sum = sum(self.blockchain.chain_state.get_utxo(tx_in).value for tx_in in tx.tx_ins)
            output_sum = sum(tx_out.value for tx_out in tx.tx_outs)
            return input_sum - output_sum
        except (AttributeError, TypeError):
            # 如果UTXO找不到或发生其他错误，视其为无效交易，费用为-1
            return -1
    async def add_transaction(self, tx: Transaction) -> bool:
        """
        验证一笔交易并尝试将其添加到内存池中，增加双花检查。
        """
        tx_hash = tx.hash()
        if tx_hash in self.transactions:
            log.debug(f"Transaction {tx_hash.hex()} already in mempool.")
            return False

        # 1. 核心状态验证 (UTXO是否存在, 签名是否正确)
        if not BlockValidator.check_tx(tx, self.blockchain.chain_state):
            log.warning(f"Transaction {tx_hash.hex()} failed core validation.")
            return False

        # 2. Mempool 内双花检查
        for tx_in in tx.tx_ins:
            utxo_ref = f"{tx_in.prev_tx_hash.hex()}:{tx_in.prev_tx_out_index}"
            if utxo_ref in self.spent_utxos:
                log.warning(f"Double spend attempt detected for UTXO {utxo_ref} in transaction {tx_hash.hex()}. Rejected.")
                return False

        # 验证通过，将交易添加到mempool
        self.transactions[tx_hash] = tx
        
        # 将此交易花费的UTXO加入到已花费集合
        for tx_in in tx.tx_ins:
            utxo_ref = f"{tx_in.prev_tx_hash.hex()}:{tx_in.prev_tx_out_index}"
            self.spent_utxos.add(utxo_ref)

        log.info(f"Added transaction {tx_hash.hex()} to mempool.")
        await self.event_bus.publish('new_tx_validated', tx)
        return True

    def remove_transaction(self, tx_hash):
        """从mempool中移除一笔交易，并清理其花费的UTXO记录。"""
        if tx_hash in self.transactions:
            tx_to_remove = self.transactions[tx_hash]
            del self.transactions[tx_hash]
            
            # 从已花费集合中移除对应的UTXO
            for tx_in in tx_to_remove.tx_ins:
                utxo_ref = f"{tx_in.prev_tx_hash.hex()}:{tx_in.prev_tx_out_index}"
                self.spent_utxos.discard(utxo_ref) # 使用discard避免key不存在时出错

    async def on_block_validated(self, block_header):
        """
        [EventBus 调用] 当一个新区块被确认时，清理内存池中已打包的交易。
        """
        block = self.blockchain.block_storage.read_block(block_header['file_index'], block_header['offset'])
        if not block:
            log.error(f"Could not read block for cleanup: {block_header['block_hash']}")
            return
            
        for tx in block.transactions:
            self.remove_transaction(tx.hash())
