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
    这在链重组时验证新区块的有效性时非常有用。
    """
    def __init__(self, chain_state: 'ChainState'):
        """
        初始化缓存视图。
        
        Args:
            chain_state: 原始的ChainState对象
        """
        self.chain_state = chain_state
        # 跟踪添加的UTXO (key: utxo_key, value: TxOut)
        self.added_utxos: Dict[bytes, TxOut] = {}
        # 跟踪删除的UTXO (key: utxo_key, value: TxOut)
        self.removed_utxos: Dict[bytes, TxOut] = {}

    def get_utxo(self, tx_input: TxIn) -> Optional[TxOut]:
        """
        获取UTXO，优先从缓存中查找，然后从主链状态中查找。
        
        Args:
            tx_input: 交易输入
            
        Returns:
            TxOut: UTXO对象，如果找不到则返回None
        """
        key = self.chain_state.get_utxo_key(tx_input)
        
        # 首先检查是否在新增的UTXO中
        if key in self.added_utxos:
            return self.added_utxos[key]
        
        # 然后检查是否在被删除的UTXO中
        if key in self.removed_utxos:
            return None
            
        # 最后从主链状态中获取
        return self.chain_state.get_utxo(tx_input)

    def apply_block(self, block: 'Block'):
        """
        模拟应用一个区块的变更到UTXO集。
        
        Args:
            block: 需要应用的区块
        """
        for tx in block.transactions:
            # 1. 删除被花费的UTXO (除了coinbase)
            if not tx.is_coinbase():
                for tx_in in tx.tx_ins:
                    key = self.chain_state.get_utxo_key(tx_in)
                    # 如果这个UTXO在added_utxos中，从added_utxos中删除
                    if key in self.added_utxos:
                        del self.added_utxos[key]
                    else:
                        # 否则，需要从主链状态中获取并移到removed_utxos中
                        utxo = self.chain_state.get_utxo(tx_in)
                        if utxo is not None:
                            self.removed_utxos[key] = utxo
            
            # 2. 添加新的UTXO
            tx_hash = tx.hash()
            for i, tx_out in enumerate(tx.tx_outs):
                key = tx_hash + i.to_bytes(4, 'little')
                self.added_utxos[key] = tx_out

    def revert_block(self, block: 'Block', spent_utxos: List[Tuple[TxIn, TxOut]]):
        """
        模拟回滚一个区块对UTXO集的修改。
        
        Args:
            block: 需要回滚的区块
            spent_utxos: 区块被花费的UTXO列表
        """
        # 1. 删除这个区块产生的新UTXO
        for tx in block.transactions:
            tx_hash = tx.hash()
            for i in range(len(tx.tx_outs)):
                key = tx_hash + i.to_bytes(4, 'little')
                if key in self.added_utxos:
                    del self.added_utxos[key]
                
        # 2. 重新将被花费的UTXO加回来
        for tx_in, tx_out in spent_utxos:
            key = self.chain_state.get_utxo_key(tx_in)
            # 从removed_utxos中移除，因为它现在又有效了
            if key in self.removed_utxos:
                del self.removed_utxos[key]


class ChainState:
    """
    管理UTXO集 (使用RocksDB)。
    """
    def __init__(self, rocksdb: RocksDBWrapper):
        self.db =rocksdb

    def get_utxo_key(self, tx_input: TxIn) -> bytes:
        """生成用于RocksDB的UTXO键。"""
        return tx_input.prev_tx_hash + tx_input.prev_tx_out_index.to_bytes(4, 'little')

    def get_utxo(self, tx_input: TxIn) -> TxOut:
        """
        根据交易输入，查找对应的UTXO。
        如果找不到，返回 None。
        """
        key = self.get_utxo_key(tx_input)
        value_bytes = self.db.get(key)
        
        if value_bytes is None:
            return None
            
        # 注意: TxOut的反序列化需要一个stream, 我们需要模拟它
        stream  = io.BytesIO(value_bytes)
        return TxOut.deserialize(stream)

    def apply_block(self, block: 'Block'):
        """
        核心功能: 应用一个区块的变更到UTXO集。同时更新状态为主链状态
        - 删除所有被花费的UTXO。
        - 添加所有新产生的UTXO。
        这个操作是原子性的。
        """
        batch = self.db.new_batch()
        
        for tx in block.transactions:
            # 1. 删除被花费的UTXO (除了coinbase)
            if not tx.is_coinbase():
                for tx_in in tx.tx_ins:
                    key = self.get_utxo_key(tx_in)
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
            key = self.get_utxo_key(tx_in)
            value = tx_out.serialize()
            batch.add(key, value)
            
        self.db.write_batch(batch)

    def close(self):
        # RocksDB没有一个明确的close方法，当对象被垃圾回收时会自动处理
        del self.db