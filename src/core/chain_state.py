"""
chain_state.py
管理UTXO集，使用RocksDB作为后端。
它提供了对UTXO的查询、应用和回滚操作。
"""
import io
import logging
from typing import Optional, List, Tuple
from storage.rocksdb_wrapper import RocksDBWrapper
from .transaction import TxOut, TxIn
from .block import Block

log = logging.getLogger(__name__)

class ChainState:
    """
    封装对UTXO数据库的所有操作。
    """
    def __init__(self, db: RocksDBWrapper):
        self.db = db

    def get_utxo_key(self, tx_in: TxIn) -> bytes:
        """根据TxIn生成用于数据库查询的key。"""
        return tx_in.prev_tx_hash + tx_in.prev_tx_out_index.to_bytes(4, 'little')

    def get_utxo(self, tx_in: TxIn) -> Optional[TxOut]:
        """
        根据交易输入（引用）查找并返回一个UTXO（交易输出）。
        """
        key = self.get_utxo_key(tx_in)
        utxo_data = self.db.get(key)
        if utxo_data:
            return TxOut.deserialize(io.BytesIO(utxo_data))
        return None

    def apply_block(self, block: 'Block') -> List[Tuple[TxIn, TxOut]]:
        """
        核心功能: 应用一个区块的变更到UTXO集。
        这个操作是原子性的。
        [已修改]：此方法现在会返回一个列表，其中包含所有在此区块中被花费的UTXO的详细信息。
        """
        batch = self.db.new_batch()
        spent_utxos_for_undo = [] # 用于存储“退货小票”信息

        # 1. 添加新的UTXO
        for tx in block.transactions:
            tx_hash = tx.hash()
            for i, tx_out in enumerate(tx.tx_outs):
                key = tx_hash + i.to_bytes(4, 'little')
                value = tx_out.serialize()
                batch.add(key, value)

        # 2. 删除被花费的UTXO (除了coinbase)
        for tx in block.transactions:
            if not tx.is_coinbase():
                for tx_in in tx.tx_ins:
                    # 在删除前，先获取这个UTXO的完整信息
                    utxo_to_spend = self.get_utxo(tx_in)
                    if utxo_to_spend:
                        # 将（输入引用，被花费的输出详情）存起来用于生成撤销记录
                        spent_utxos_for_undo.append((tx_in, utxo_to_spend))

                    key = self.get_utxo_key(tx_in)
                    batch.delete(key)

        self.db.write_batch(batch)

        # 返回被花费的UTXO列表
        return spent_utxos_for_undo

    def revert_block(self, block: 'Block', spent_utxos: List[Tuple[TxIn, TxOut]]):
        """
        核心功能: 回滚一个区块的变更。
        这个操作是原子性的。
        """
        batch = self.db.new_batch()

        # 1. 删除这个区块创造的新UTXO
        for tx in block.transactions:
            tx_hash = tx.hash()
            for i, tx_out in enumerate(tx.tx_outs):
                key = tx_hash + i.to_bytes(4, 'little')
                batch.delete(key)

        # 2. 恢复被这个区块花掉的旧UTXO
        for tx_in, tx_out in spent_utxos:
            key = self.get_utxo_key(tx_in)
            value = tx_out.serialize()
            batch.add(key, value)

        self.db.write_batch(batch)

    def close(self):
        self.db.close()

class ChainStateCacheView:
    """
    一个UTXO集的缓存视图，用于在内存中模拟区块的应用和回滚，
    主要用于链重组时的验证过程。
    """
    def __init__(self, parent_state: 'ChainState'):
        self.parent = parent_state
        self.cache = {} # {key: value}, value为None表示已删除

    def get_utxo(self, tx_in: TxIn) -> Optional[TxOut]:
        key = self.parent.get_utxo_key(tx_in)
        if key in self.cache:
            value = self.cache[key]
            return TxOut.deserialize(value) if value else None
        return self.parent.get_utxo(tx_in)

    def apply_block(self, block: 'Block'):
        # 模拟添加
        for tx in block.transactions:
            tx_hash = tx.hash()
            for i, tx_out in enumerate(tx.tx_outs):
                key = tx_hash + i.to_bytes(4, 'little')
                self.cache[key] = tx_out.serialize()
        # 模拟删除
        for tx in block.transactions:
            if not tx.is_coinbase():
                for tx_in in tx.tx_ins:
                    key = self.parent.get_utxo_key(tx_in)
                    self.cache[key] = None

    def revert_block(self, block: 'Block', spent_utxos: List[Tuple[TxIn, TxOut]]):
        # 模拟删除新UTXO
        for tx in block.transactions:
            tx_hash = tx.hash()
            for i, tx_out in enumerate(tx.tx_outs):
                key = tx_hash + i.to_bytes(4, 'little')
                self.cache[key] = None
        # 模拟恢复旧UTXO
        for tx_in, tx_out in spent_utxos:
            key = self.parent.get_utxo_key(tx_in)
            self.cache[key] = tx_out.serialize()

    def get_batch(self):
        """将缓存中的变更转换为一个RocksDB的批处理对象。"""
        batch = self.parent.db.new_batch()
        for key, value in self.cache.items():
            if value is None:
                batch.delete(key)
            else:
                batch.add(key, value)
        return batch