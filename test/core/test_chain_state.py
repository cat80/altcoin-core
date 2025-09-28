import unittest
import tempfile
import shutil
import os
import sys

# 添加src目录到Python路径中
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from core.chain_state import ChainState
from core.transaction import Transaction, TxIn, TxOut


class TestChainState(unittest.TestCase):
    def setUp(self):
        """在每个测试方法之前创建临时目录"""
        self.temp_dir = tempfile.mkdtemp()
        self.chain_state = ChainState(self.temp_dir)

    def tearDown(self):
        """在每个测试方法之后清理临时目录"""
        self.chain_state.close()
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_get_and_put_utxo(self):
        """测试获取和存储UTXO"""
        # 创建一个测试交易输出
        tx_out = TxOut(100000000, b"test_locking_script")
        
        # 创建一个测试交易输入
        tx_in = TxIn(
            prev_tx_hash=b'\x01' * 32,
            prev_tx_out_index=0,
            unlocking_script=b"test_unlocking_script"
        )
        
        # 存储UTXO
        key = self.chain_state._get_utxo_key(tx_in)
        self.chain_state.db.put(key, tx_out.serialize())
        
        # 获取UTXO
        retrieved_tx_out = self.chain_state.get_utxo(tx_in)
        
        # 验证获取的UTXO
        self.assertIsNotNone(retrieved_tx_out)
        self.assertEqual(retrieved_tx_out.value, tx_out.value)
        self.assertEqual(retrieved_tx_out.locking_script, tx_out.locking_script)

    def test_get_nonexistent_utxo(self):
        """测试获取不存在的UTXO"""
        # 创建一个测试交易输入
        tx_in = TxIn(
            prev_tx_hash=b'\x01' * 32,
            prev_tx_out_index=0,
            unlocking_script=b"test_unlocking_script"
        )
        
        # 尝试获取不存在的UTXO
        retrieved_tx_out = self.chain_state.get_utxo(tx_in)
        
        # 应该返回None
        self.assertIsNone(retrieved_tx_out)

    def test_apply_block(self):
        """测试应用区块到UTXO集"""
        # 创建一个测试区块（简单模拟）
        class MockBlock:
            def __init__(self, transactions):
                self.transactions = transactions
        
        # 创建一个花费的交易（非coinbase）
        spend_tx_in = TxIn(
            prev_tx_hash=b'\x02' * 32,
            prev_tx_out_index=0,
            unlocking_script=b"test_unlocking_script"
        )
        
        spend_tx = Transaction(
            version=1,
            tx_ins=[spend_tx_in],
            tx_outs=[TxOut(50000000, b"new_locking_script")],
            lock_time=0
        )
        
        # 创建一个coinbase交易
        coinbase_tx = Transaction(
            version=1,
            tx_ins=[TxIn.create_coinbase_txin(b"test")],
            tx_outs=[TxOut(5000000000, b"coinbase_locking_script")],
            lock_time=0
        )
        
        block = MockBlock([coinbase_tx, spend_tx])
        
        # 预先添加一个UTXO用于被花费
        key = self.chain_state._get_utxo_key(spend_tx_in)
        utxo_to_spend = TxOut(100000000, b"original_locking_script")
        self.chain_state.db.put(key, utxo_to_spend.serialize())
        
        # 应用区块
        self.chain_state.apply_block(block)
        
        # 验证被花费的UTXO已被删除
        retrieved_spent_utxo = self.chain_state.get_utxo(spend_tx_in)
        self.assertIsNone(retrieved_spent_utxo)
        
        # 验证新的UTXO已添加
        # 对于coinbase交易
        coinbase_tx_in = TxIn(
            prev_tx_hash=coinbase_tx.hash(),
            prev_tx_out_index=0,
            unlocking_script=b""
        )
        retrieved_coinbase_utxo = self.chain_state.get_utxo(coinbase_tx_in)
        self.assertIsNotNone(retrieved_coinbase_utxo)
        self.assertEqual(retrieved_coinbase_utxo.value, 5000000000)
        
        # 对于普通交易的输出
        new_tx_in = TxIn(
            prev_tx_hash=spend_tx.hash(),
            prev_tx_out_index=0,
            unlocking_script=b""
        )
        retrieved_new_utxo = self.chain_state.get_utxo(new_tx_in)
        self.assertIsNotNone(retrieved_new_utxo)
        self.assertEqual(retrieved_new_utxo.value, 50000000)

    def test_revert_block(self):
        """测试回滚区块对UTXO集的修改"""
        # 创建一个测试区块（简单模拟）
        class MockBlock:
            def __init__(self, transactions):
                self.transactions = transactions
        
        # 创建一个coinbase交易
        coinbase_tx = Transaction(
            version=1,
            tx_ins=[TxIn.create_coinbase_txin(b"test")],
            tx_outs=[TxOut(5000000000, b"coinbase_locking_script")],
            lock_time=0
        )
        
        block = MockBlock([coinbase_tx])
        
        # 准备被花费的UTXO列表
        spent_utxo_tx_in = TxIn(
            prev_tx_hash=b'\x03' * 32,
            prev_tx_out_index=0,
            unlocking_script=b""
        )
        spent_utxo_tx_out = TxOut(100000000, b"spent_locking_script")
        spent_utxos = [(spent_utxo_tx_in, spent_utxo_tx_out)]
        
        # 回滚区块
        self.chain_state.revert_block(block, spent_utxos)
        
        # 验证区块产生的UTXO已被删除（这里无法直接验证，因为没有实际应用区块）
        # 验证被花费的UTXO已重新添加
        retrieved_spent_utxo = self.chain_state.get_utxo(spent_utxo_tx_in)
        self.assertIsNotNone(retrieved_spent_utxo)
        self.assertEqual(retrieved_spent_utxo.value, 100000000)
        self.assertEqual(retrieved_spent_utxo.locking_script, b"spent_locking_script")


if __name__ == '__main__':
    unittest.main()