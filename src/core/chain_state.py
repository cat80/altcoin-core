"""
chain_state.py
负责管理区块链的“当前状态”，主要是UTXO集。
使用 RocksDB 作为高性能的键值存储引擎。
"""
from typing import List,Tuple
from storage import RocksDBWrapper
from .transaction import TxIn, TxOut
import io
class ChainState:
    """
    管理UTXO集 (使用RocksDB)。
    """
    def __init__(self, rocksdb_dir: str):
        self.db =RocksDBWrapper(rocksdb_dir)

    def _get_utxo_key(self, tx_input: TxIn) -> bytes:
        """生成用于RocksDB的UTXO键。"""
        return tx_input.prev_tx_hash + tx_input.prev_tx_out_index.to_bytes(4, 'little')

    def get_utxo(self, tx_input: TxIn) -> TxOut:
        """
        根据交易输入，查找对应的UTXO。
        如果找不到，返回 None。
        """
        key = self._get_utxo_key(tx_input)
        value_bytes = self.db.get(key)
        
        if value_bytes is None:
            return None
            
        # 注意: TxOut的反序列化需要一个stream, 我们需要模拟它
        stream  = io.BytesIO(value_bytes)
        return TxOut.deserialize(stream)

    def apply_block(self, block: 'Block'):
        """
        核心功能: 应用一个区块的变更到UTXO集。
        - 删除所有被花费的UTXO。
        - 添加所有新产生的UTXO。
        这个操作是原子性的。
        """
        batch = self.db.new_batch()
        
        for tx in block.transactions:
            # 1. 删除被花费的UTXO (除了coinbase)
            if not tx.is_coinbase():
                for tx_in in tx.tx_ins:
                    key = self._get_utxo_key(tx_in)
                    batch.delete(key)
            
            # 2. 添加新的UTXO
            tx_hash = tx.hash()
            for i, tx_out in enumerate(tx.tx_outs):
                key = tx_hash + i.to_bytes(4, 'little')
                value = tx_out.serialize()
                batch.add(key, value)
                
        self.db.write_batch(batch)

    def revert_block(self, block: 'Block', spent_utxos: List[Tuple[TxIn, TxOut]]):
        """
        核心功能: 回滚一个区块对UTXO集的修改。
        这在链重组时至关重要。
        - 删除该区块产生的新UTXO。
        - 将被该区块花费的UTXO重新加回到UTXO集中。
        
        Args:
            block: 需要回滚的区块。
            spent_utxos: 一个列表，包含了这个区块花费掉的UTXO的完整信息 (TxIn, TxOut)。
                         这些信息在应用区块时是已知的，但在回滚时必须从外部提供，
                         因为仅靠区块本身无法知道被花费的UTXO的value和locking_script。
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
            key = self._get_utxo_key(tx_in)
            value = tx_out.serialize()
            batch.add(key, value)
            
        self.db.write_batch(batch)

    def close(self):
        # RocksDB没有一个明确的close方法，当对象被垃圾回收时会自动处理
        del self.db
