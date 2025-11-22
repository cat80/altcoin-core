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

        # 订阅区块确认事件，以便清理已打包的交易
        # 注意：这里假设 'block_validated' 事件会在区块成功加入主链后发布
        self.event_bus.subscribe('block_validated', self.on_block_validated)
        # 收到新的区块
        self.event_bus.subscribe("recv_new_tx",self.add_transaction)
    def get_local_pack_transactions(self):
        # 返回一个副本，在本地主链可以打包的一交易
        # 这里对transaction的有效性做一下检查，如果是无效区块直接删除，
        # 这里会存在的问题就是，如果本地的链未更新到最新，
        pack_txs = []
        remove_keys = []
        for tx_hash,tx in self.transactions.items():
            if not BlockValidator.check_tx(tx, self.blockchain.chain_state):
                log.warning(f"Transaction {tx_hash.hex()} failed validation.delete from mempool")
                remove_keys.append(remove_keys)
            else:
                pack_txs.append(tx)
        # 清除无效的key
        [  self.remove_transaction(key) for key in remove_keys]
        return pack_txs


    async def add_transaction(self, tx: Transaction) -> bool:
        """
        验证一笔交易并尝试将其添加到内存池中。
        这是 Mempool 的核心入口，需要执行完整的交易验证。
        """
        tx_hash = tx.hash()
        if tx_hash in self.transactions:
            log.debug(f"Transaction {tx_hash.hex()} already in mempool.")
            return False # 已经存在，不算失败，但也不重复添加

        # 使用 BlockValidator 中的静态方法来验证交易的有效性
        # 注意：这里我们传入 chain_state 来检查 UTXO 和双花问题
        if not BlockValidator.check_tx(tx, self.blockchain.chain_state):
            log.warning(f"Transaction {tx_hash.hex()} failed validation.")
            return False

        self.transactions[tx_hash] = tx
        log.info(f"Added transaction {tx_hash.hex()} to mempool.")
        # 验证通过并添加后，发布事件通知其他模块
        await self.event_bus.publish('new_tx_validated', tx)
        return True

    def remove_transaction(self, tx_hash):
        if tx_hash in self.transactions:
            del self.transactions[tx_hash]

    async def on_block_validated(self, block_header):
        """
        [EventBus 调用] 当一个新区块被确认时，清理内存池中已打包的交易。
        """
        """当一个新区块被确认时，从中移除已打包的交易"""
        #  file_index: int, offset:
        block = self.blockchain.block_storage.read_block(block_header['file_index'],block_header['offset'])
        for tx in block.transactions: # 删除
            self.remove_transaction(tx.hash())
