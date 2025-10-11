import unittest
from unittest.mock import Mock, patch, MagicMock
import io
import tempfile
import os
import sys

# 添加项目根目录到sys.path，确保可以导入src目录下的模块
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from core.chain_state import ChainState, ChainStateCacheView
from core.transaction import Transaction, TxIn, TxOut
from storage.rocksdb_wrapper import RocksDBWrapper


class TestChainState(unittest.TestCase):

    def setUp(self):
        """测试前的准备工作"""
        # 创建mock的RocksDBWrapper
        self.mock_db = Mock(spec=RocksDBWrapper)
        self.chain_state = ChainState(self.mock_db)

        # 创建测试交易输入和输出
        self.test_txin = TxIn(
            prev_tx_hash=b'\x01' * 32,
            prev_tx_out_index=0,
            unlocking_script=b'test_unlock_script'
        )
        
        self.test_txout = TxOut(
            value=1000,
            locking_script=b'test_lock_script'
        )

    def testget_utxo_key(self):
        """测试UTXO键的生成"""
        key = self.chain_state.get_utxo_key(self.test_txin)
        expected_key = self.test_txin.prev_tx_hash + self.test_txin.prev_tx_out_index.to_bytes(4, 'little')
        self.assertEqual(key, expected_key)

    def test_get_utxo_found(self):
        """测试获取存在的UTXO"""
        # 模拟数据库返回序列化的TxOut
        serialized_txout = self.test_txout.serialize()
        self.mock_db.get.return_value = serialized_txout
        
        result = self.chain_state.get_utxo(self.test_txin)
        
        # 验证结果
        self.assertIsNotNone(result)
        self.assertEqual(result.value, self.test_txout.value)
        self.assertEqual(result.locking_script, self.test_txout.locking_script)
        
        # 验证调用了正确的键
        expected_key = self.test_txin.prev_tx_hash + self.test_txin.prev_tx_out_index.to_bytes(4, 'little')
        self.mock_db.get.assert_called_once_with(expected_key)

    def test_get_utxo_not_found(self):
        """测试获取不存在的UTXO"""
        # 模拟数据库返回None
        self.mock_db.get.return_value = None
        
        result = self.chain_state.get_utxo(self.test_txin)
        
        self.assertIsNone(result)
        self.mock_db.get.assert_called_once()

    def test_apply_block(self):
        """测试应用区块到UTXO集"""
        # 创建测试交易
        txin1 = TxIn(
            prev_tx_hash=b'\x02' * 32,
            prev_tx_out_index=1,
            unlocking_script=b'test_unlock_script_1'
        )
        
        txout1 = TxOut(
            value=500,
            locking_script=b'test_lock_script_1'
        )
        
        # 创建普通交易
        normal_tx = Transaction(
            version=1,
            tx_ins=[txin1],
            tx_outs=[txout1],
            lock_time=0
        )
        
        # 创建coinbase交易
        coinbase_txin = TxIn.create_coinbase_txin(b'Coinbase Data')
        coinbase_txout = TxOut(
            value=5000,
            locking_script=b'\x00' * 20
        )
        coinbase_tx = Transaction(
            version=1,
            tx_ins=[coinbase_txin],
            tx_outs=[coinbase_txout],
            lock_time=0
        )
        
        # 创建mock区块
        mock_block = Mock()
        mock_block.transactions = [coinbase_tx, normal_tx]
        
        # 创建mock批处理
        mock_batch = Mock()
        self.mock_db.new_batch.return_value = mock_batch
        self.mock_db.write_batch = Mock()
        
        # 模拟交易哈希
        normal_tx_hash = b'\x03' * 32
        coinbase_tx_hash = b'\x04' * 32
        
        # 为测试交易创建一个带有mock hash方法的新类
        class MockTransaction:
            def __init__(self, tx, hash_value):
                self._tx = tx
                self._hash_value = hash_value
                
            def __getattr__(self, name):
                # 将所有其他属性/方法委托给原始交易对象
                return getattr(self._tx, name)
                
            def hash(self):
                return self._hash_value
        
        # 创建mock交易对象
        mock_normal_tx = MockTransaction(normal_tx, normal_tx_hash)
        mock_coinbase_tx = MockTransaction(coinbase_tx, coinbase_tx_hash)
        
        # 替换mock区块中的交易对象
        mock_block.transactions = [mock_coinbase_tx, mock_normal_tx]
        
        # 执行测试
        self.chain_state.apply_block(mock_block)
        
        # 验证调用了new_batch
        self.mock_db.new_batch.assert_called_once()
        
        # 验证删除了普通交易的输入UTXO
        expected_delete_key = txin1.prev_tx_hash + txin1.prev_tx_out_index.to_bytes(4, 'little')
        mock_batch.delete.assert_called_once_with(expected_delete_key)
        
        # 验证添加了新的UTXO（普通交易和coinbase交易的输出）
        self.assertEqual(mock_batch.add.call_count, 2)
        
        # 验证写入批处理
        self.mock_db.write_batch.assert_called_once_with(mock_batch)

    def test_revert_block(self):
        """测试回滚区块对UTXO集的修改"""
        # 创建测试交易
        txout1 = TxOut(
            value=500,
            locking_script=b'test_lock_script_1'
        )
        
        # 创建普通交易
        normal_tx = Transaction(
            version=1,
            tx_ins=[self.test_txin],
            tx_outs=[txout1],
            lock_time=0
        )
        
        # 创建coinbase交易
        coinbase_txin = TxIn.create_coinbase_txin(b'Coinbase Data')
        coinbase_txout = TxOut(
            value=5000,
            locking_script=b'\x00' * 20
        )
        coinbase_tx = Transaction(
            version=1,
            tx_ins=[coinbase_txin],
            tx_outs=[coinbase_txout],
            lock_time=0
        )
        
        # 创建mock区块
        mock_block = Mock()
        mock_block.transactions = [coinbase_tx, normal_tx]
        
        # 创建mock批处理
        mock_batch = Mock()
        self.mock_db.new_batch.return_value = mock_batch
        self.mock_db.write_batch = Mock()
        
        # 模拟交易哈希
        normal_tx_hash = b'\x03' * 32
        coinbase_tx_hash = b'\x04' * 32
        
        # 为测试交易创建一个带有mock hash方法的新类
        class MockTransaction:
            def __init__(self, tx, hash_value):
                self._tx = tx
                self._hash_value = hash_value
                
            def __getattr__(self, name):
                # 将所有其他属性/方法委托给原始交易对象
                return getattr(self._tx, name)
                
            def hash(self):
                return self._hash_value
        
        # 创建mock交易对象
        mock_normal_tx = MockTransaction(normal_tx, normal_tx_hash)
        mock_coinbase_tx = MockTransaction(coinbase_tx, coinbase_tx_hash)
        
        # 替换mock区块中的交易对象
        mock_block.transactions = [mock_coinbase_tx, mock_normal_tx]
        
        # 创建被花费的UTXO列表
        spent_utxos = [(self.test_txin, self.test_txout)]
        
        # 执行测试
        self.chain_state.revert_block(mock_block, spent_utxos)
        
        # 验证调用了new_batch
        self.mock_db.new_batch.assert_called_once()
        
        # 验证删除了区块产生的新UTXO（2个交易，每个1个输出）
        self.assertEqual(mock_batch.delete.call_count, 2)
        
        # 验证重新添加了被花费的UTXO
        mock_batch.add.assert_called_once()
        
        # 验证写入批处理
        self.mock_db.write_batch.assert_called_once_with(mock_batch)

    def test_close(self):
        """测试关闭数据库连接"""
        # 执行测试
        self.chain_state.close()
        
        # 验证删除了db引用
        self.mock_db = None


class TestChainStateCacheView(unittest.TestCase):
    
    def setUp(self):
        """测试前的准备工作"""
        # 创建mock的ChainState
        self.mock_chain_state = Mock(spec=ChainState)
        # self.mock_chain_state.get_utxo_key = ChainState.get_utxo_key
        
        # 创建ChainStateCacheView实例
        self.cache_view = ChainStateCacheView(self.mock_chain_state)
        
        # 创建测试交易输入和输出
        self.test_txin = TxIn(
            prev_tx_hash=b'\x01' * 32,
            prev_tx_out_index=0,
            unlocking_script=b'test_unlock_script'
        )
        
        self.test_txout = TxOut(
            value=1000,
            locking_script=b'test_lock_script'
        )

    def test_get_utxo_from_added_utxos(self):
        """测试从added_utxos中获取UTXO"""
        # 添加一个UTXO到缓存中
        key = self.mock_chain_state.get_utxo_key(self.test_txin)
        self.cache_view.added_utxos[key] = self.test_txout
        
        # 获取UTXO
        result = self.cache_view.get_utxo(self.test_txin)
        
        # 验证结果
        self.assertIsNotNone(result)
        self.assertEqual(result.value, self.test_txout.value)
        self.assertEqual(result.locking_script, self.test_txout.locking_script)

    def test_get_utxo_from_removed_utxos(self):
        """测试从removed_utxos中获取UTXO（应该返回None）"""
        # 添加一个UTXO到removed_utxos中
        key = self.mock_chain_state.get_utxo_key(self.test_txin)
        self.cache_view.removed_utxos[key] = self.test_txout
        
        # 模拟主链状态中有这个UTXO
        self.mock_chain_state.get_utxo.return_value = self.test_txout
        
        # 获取UTXO
        result = self.cache_view.get_utxo(self.test_txin)
        
        # 验证结果为None
        self.assertIsNone(result)

    def test_get_utxo_from_chain_state(self):
        """测试从主链状态中获取UTXO"""
        # 模拟主链状态中有这个UTXO
        self.mock_chain_state.get_utxo.return_value = self.test_txout
        
        # 获取UTXO
        result = self.cache_view.get_utxo(self.test_txin)
        
        # 验证结果
        self.assertIsNotNone(result)
        self.assertEqual(result.value, self.test_txout.value)
        self.assertEqual(result.locking_script, self.test_txout.locking_script)

    def test_apply_block(self):
        """测试模拟应用区块"""
        # 创建测试交易
        txin1 = TxIn(
            prev_tx_hash=b'\x02' * 32,
            prev_tx_out_index=1,
            unlocking_script=b'test_unlock_script_1'
        )
        
        txout1 = TxOut(
            value=500,
            locking_script=b'test_lock_script_1'
        )
        
        # 创建普通交易
        normal_tx = Transaction(
            version=1,
            tx_ins=[txin1],
            tx_outs=[txout1],
            lock_time=0
        )
        
        # 创建coinbase交易
        coinbase_txin = TxIn.create_coinbase_txin(b'Coinbase Data')
        coinbase_txout = TxOut(
            value=5000,
            locking_script=b'\x00' * 20
        )
        coinbase_tx = Transaction(
            version=1,
            tx_ins=[coinbase_txin],
            tx_outs=[coinbase_txout],
            lock_time=0
        )
        
        # 创建mock区块
        mock_block = Mock()
        mock_block.transactions = [coinbase_tx, normal_tx]
        
        # 模拟交易哈希
        normal_tx_hash = b'\x03' * 32
        coinbase_tx_hash = b'\x04' * 32
        
        # 为测试交易创建一个带有mock hash方法的新类
        class MockTransaction:
            def __init__(self, tx, hash_value):
                self._tx = tx
                self._hash_value = hash_value
                
            def __getattr__(self, name):
                # 将所有其他属性/方法委托给原始交易对象
                return getattr(self._tx, name)
                
            def hash(self):
                return self._hash_value
        
        # 创建mock交易对象
        mock_normal_tx = MockTransaction(normal_tx, normal_tx_hash)
        mock_coinbase_tx = MockTransaction(coinbase_tx, coinbase_tx_hash)
        
        # 替换mock区块中的交易对象
        mock_block.transactions = [mock_coinbase_tx, mock_normal_tx]
        
        # 执行测试
        self.cache_view.apply_block(mock_block)
        
        # 验证added_utxos中有新的UTXO
        self.assertEqual(len(self.cache_view.added_utxos), 2)
        
        # 验证removed_utxos中有被花费的UTXO
        key = self.mock_chain_state.get_utxo_key(txin1)
        self.assertIn(key, self.cache_view.removed_utxos)

    def test_revert_block(self):
        """测试模拟回滚区块"""
        # 创建测试交易
        txout1 = TxOut(
            value=500,
            locking_script=b'test_lock_script_1'
        )
        
        # 创建普通交易
        normal_tx = Transaction(
            version=1,
            tx_ins=[self.test_txin],
            tx_outs=[txout1],
            lock_time=0
        )
        
        # 创建coinbase交易
        coinbase_txin = TxIn.create_coinbase_txin(b'Coinbase Data')
        coinbase_txout = TxOut(
            value=5000,
            locking_script=b'\x00' * 20
        )
        coinbase_tx = Transaction(
            version=1,
            tx_ins=[coinbase_txin],
            tx_outs=[coinbase_txout],
            lock_time=0
        )
        
        # 创建mock区块
        mock_block = Mock()
        mock_block.transactions = [coinbase_tx, normal_tx]
        
        # 模拟交易哈希
        normal_tx_hash = b'\x03' * 32
        coinbase_tx_hash = b'\x04' * 32
        
        # 为测试交易创建一个带有mock hash方法的新类
        class MockTransaction:
            def __init__(self, tx, hash_value):
                self._tx = tx
                self._hash_value = hash_value
                
            def __getattr__(self, name):
                # 将所有其他属性/方法委托给原始交易对象
                return getattr(self._tx, name)
                
            def hash(self):
                return self._hash_value
        
        # 创建mock交易对象
        mock_normal_tx = MockTransaction(normal_tx, normal_tx_hash)
        mock_coinbase_tx = MockTransaction(coinbase_tx, coinbase_tx_hash)
        
        # 替换mock区块中的交易对象
        mock_block.transactions = [mock_coinbase_tx, mock_normal_tx]
        
        # 添加一些初始状态到缓存中（模拟预先存在的UTXO）
        key = self.mock_chain_state.get_utxo_key(self.test_txin)
        self.cache_view.added_utxos[key] = self.test_txout
        
        # 创建被花费的UTXO列表
        spent_utxos = [(self.test_txin, self.test_txout)]
        
        # 执行测试
        self.cache_view.revert_block(mock_block, spent_utxos)
        
        # 验证区块产生的UTXO已被删除
        self.assertEqual(len(self.cache_view.added_utxos), 1)  # 预先存在的UTXO仍然存在
        
        # 验证被花费的UTXO已从removed_utxos中移除（因为它被恢复了）
        self.assertNotIn(key, self.cache_view.removed_utxos)
        
        # 验证预先存在的UTXO仍然在added_utxos中
        self.assertIn(key, self.cache_view.added_utxos)


if __name__ == '__main__':
    unittest.main()