"""
chain_state.py
负责管理区块链的"当前状态"，主要是UTXO集。
使用 RocksDB 作为高性能的键值存储引擎。
"""
from typing import List,Tuple,Dict,Optional
from storage import RocksDBWrapper
from .transaction import TxIn, TxOut
import io

class ChainStateCacheView:
    """
    ChainState的缓存视图，用于在不影响主链状态的情况下模拟UTXO集的变化。
    在模拟的同时，会预先构建好一个RocksDB的WriteBatch，以便验证成功后直接提交。
    """
    def __init__(self, chain_state: 'ChainState'):
        self.chain_state = chain_state
        self.utxo_cache: Dict[bytes, Optional[TxOut]] = {}
        # 预构建的数据库批处理
        self.db_batch = self.chain_state.db.new_batch()

    def get_utxo(self, tx_input: TxIn) -> Optional[TxOut]:
        key = self.chain_state.get_utxo_key(tx_input)
        if key in self.utxo_cache:
            return self.utxo_cache[key]
        
        utxo = self.chain_state.get_utxo(tx_input)
        self.utxo_cache[key] = utxo
        return utxo

    def apply_block(self, block: 'Block'):
        # 1. 添加新的UTXO
        for tx in block.transactions:
            tx_hash = tx.hash()
            for i, tx_out in enumerate(tx.tx_outs):
                key = tx_hash + i.to_bytes(4, 'little')
                self.utxo_cache[key] = tx_out
                self.db_batch.add(key, tx_out.serialize())

        # 2. 将被花费的UTXO标记为None并从数据库删除
        for tx in block.transactions:
            if not tx.is_coinbase():
                for tx_in in tx.tx_ins:
                    utxo = self.get_utxo(tx_in)
                    if utxo is not None:
                        key = self.chain_state.get_utxo_key(tx_in)
                        self.utxo_cache[key] = None
                        self.db_batch.delete(key)

    def revert_block(self, block: 'Block', spent_utxos: List[Tuple[TxIn, TxOut]]):
        # 1. 删除这个区块产生的新UTXO
        for tx in block.transactions:
            tx_hash = tx.hash()
            for i in range(len(tx.tx_outs)):
                key = tx_hash + i.to_bytes(4, 'little')
                self.utxo_cache.pop(key, None)
                self.db_batch.delete(key)
                
        # 2. 恢复被花费的UTXO
        for tx_in, tx_out in spent_utxos:
            key = self.chain_state.get_utxo_key(tx_in)
            self.utxo_cache[key] = tx_out
            self.db_batch.add(key, tx_out.serialize())

    def get_batch(self):
        """返回构建好的数据库批处理对象。"""
        return self.db_batch


class ChainState:
    """
    管理UTXO集 (使用RocksDB)。
    """
    def __init__(self, rocksdb: RocksDBWrapper):
        self.db = rocksdb

    def get_utxo_key(self, tx_input: TxIn) -> bytes:
        """生成用于RocksDB的UTXO键。"""
        return tx_input.prev_tx_hash + tx_input.prev_tx_out_index.to_bytes(4, 'little')

    def get_utxo(self, tx_input: TxIn) -> Optional[TxOut]:
        """
        根据交易输入，查找对应的UTXO。
        如果找不到，返回 None。
        """
        key = self.get_utxo_key(tx_input)
        value_bytes = self.db.get(key)
        
        if value_bytes is None:
            return None
            
        stream = io.BytesIO(value_bytes)
        return TxOut.deserialize(stream)

    def commit_utxo_batch(self, batch):
        """原子性地提交一个预构建的UTXO批处理。"""
        self.db.write_batch(batch)

    def apply_block(self, block: 'Block'):
        """
        核心功能: 应用一个区块的变更到UTXO集。
        这个操作是原子性的。
        """
        batch = self.db.new_batch()
        
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
                    key = self.get_utxo_key(tx_in)
                    batch.delete(key)
            
        self.db.write_batch(batch)

    def revert_block(self, block: 'Block', spent_utxos: List[Tuple[TxIn, TxOut]]):
        """
        核心功能: 回滚一个区块对UTXO集的修改。
        """
        batch = self.db.new_batch()
        
        # 1. 删除这个区块产生的新UTXO
        for tx in block.transactions:
            tx_hash = tx.hash()
            for i in range(len(tx.tx_outs)):
                key = tx_hash + i.to_bytes(4, 'little')
                batch.delete(key)
                
        # 2. 重新将被花费的UTXO加回来
        for tx_in, tx_out in spent_utxos:
            key = self.get_utxo_key(tx_in)
            value = tx_out.serialize()
            batch.add(key, value)
            
        self.db.write_batch(batch)

    def close(self):
        del self.db