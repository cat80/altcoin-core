import unittest
import os
import shutil
import io

from core import BlockValidator, ChainState, Transaction, TxIn, TxOut
from utils.crypto import generate_keypair, sign_data as sign_message, get_address_by_public_key
from storage import RocksDBWrapper
from config import INITIAL_BLOCK_REWARD

class TestBlockValidator(unittest.TestCase):

    def setUp(self):
        self.test_dir = "test_validator_data"
        os.makedirs(self.test_dir, exist_ok=True)

        # 创建一个临时的 ChainState 用于测试
        db_path = os.path.join(self.test_dir, 'utxo_db')
        rocks_db = RocksDBWrapper(db_path)
        self.chain_state = ChainState(rocks_db)

        # 创建一些用于测试的密钥和地址
        self.priv_key1, self.pub_key1 = generate_keypair()
        self.address1 = get_address_by_public_key(self.pub_key1)

        self.priv_key2, self.pub_key2 = generate_keypair()
        self.address2 = get_address_by_public_key(self.pub_key2)

        # 创建一个初始的UTXO并存入ChainState
        self.initial_tx_hash = b'\x11' * 32
        self.initial_utxo = TxOut(value=1000, locking_script=self.address1.encode())
        
        # 模拟一个UTXO存在于数据库中
        utxo_key = self.initial_tx_hash + b'\x00\x00\x00\x00' # index 0
        utxo_value = self.initial_utxo.serialize()
        self.chain_state.db.put(utxo_key, utxo_value)

    def tearDown(self):
        self.chain_state.close()
        if os.path.exists(self.test_dir):
            shutil.rmtree(self.test_dir)

    def _create_signed_tx(self, value=800, fee=200, priv_key=None, pub_key=None):
        """辅助函数：创建一个签过名的有效交易"""
        priv_key = priv_key or self.priv_key1
        pub_key = pub_key or self.pub_key1

        tx_in = TxIn(self.initial_tx_hash, 0, b'') # unlocking_script 稍后填充
        tx_out = TxOut(value, self.address2.encode())
        tx = Transaction(1, [tx_in], [tx_out], 0)

        # 签名
        hash_for_signing = tx.serialize(for_signing=True)
        signature = sign_message(hash_for_signing, priv_key)
        tx.tx_ins[0] = TxIn(tx_in.prev_tx_hash, tx_in.prev_tx_out_index, signature + pub_key.to_string())
        return tx

    # ==========================================================
    # Tests for check_tx (for Mempool)
    # ==========================================================

    def test_check_tx_valid(self):
        """测试一笔完全有效的交易"""
        tx = self._create_signed_tx()
        self.assertTrue(BlockValidator.check_tx(tx, self.chain_state))

    def test_check_tx_invalid_utxo_not_found(self):
        """测试花费一个不存在的UTXO"""
        tx = self._create_signed_tx()
        tx.tx_ins[0] = TxIn(b'\x22' * 32, 0, tx.tx_ins[0].unlocking_script) # 使用不存在的哈希
        self.assertFalse(BlockValidator.check_tx(tx, self.chain_state))

    def test_check_tx_invalid_insufficient_funds(self):
        """测试输入总额小于输出总额"""
        tx = self._create_signed_tx(value=1200) # 花费超过拥有的 1000
        self.assertFalse(BlockValidator.check_tx(tx, self.chain_state))

    def test_check_tx_invalid_signature(self):
        """测试无效的签名（用错误的私钥签名）"""
        tx = self._create_signed_tx(priv_key=self.priv_key2) # 用 key2 签名
        self.assertFalse(BlockValidator.check_tx(tx, self.chain_state))

    def test_check_tx_coinbase(self):
        """测试 check_tx 不应该接受 coinbase 交易"""
        coinbase_txin = TxIn.create_coinbase_txin(b'test coinbase')
        tx_out = TxOut(50, self.address1.encode())
        tx = Transaction(1, [coinbase_txin], [tx_out], 0)
        self.assertFalse(BlockValidator.check_tx(tx, self.chain_state))

    # ==========================================================
    # Tests for check_transactions_and_get_fees (for Block)
    # ==========================================================

    def test_check_transactions_valid_block(self):
        """测试一个有效的交易列表，并验证手续费计算"""
        block_height = 10
        fee = 200
        regular_tx = self._create_signed_tx(value=800) # 1000 in, 800 out -> 200 fee
        
        # Coinbase 交易应该包含区块奖励 + 手续费
        block_reward = BlockValidator.get_block_reward(block_height)
        coinbase_txout = TxOut(block_reward + fee, self.address2.encode())
        coinbase_txin = TxIn.create_coinbase_txin(f"{block_height}:".encode())
        coinbase_tx = Transaction(1, [coinbase_txin], [coinbase_txout], 0)

        transactions = [coinbase_tx, regular_tx]
        
        calculated_fee = BlockValidator.check_transactions_and_get_fees(transactions, self.chain_state, block_height)
        self.assertEqual(calculated_fee, fee)

    def test_check_transactions_fails_on_utxo_not_found(self):
        """测试交易列表，其中一个交易花费了不存在的UTXO"""
        block_height = 10
        regular_tx = self._create_signed_tx()
        # 篡改输入
        regular_tx.tx_ins[0] = TxIn(b'\x99'*32, 0, regular_tx.tx_ins[0].unlocking_script)

        coinbase_txin = TxIn.create_coinbase_txin(f"{block_height}:".encode())
        coinbase_tx = Transaction(1, [coinbase_txin], [], 0)
        
        transactions = [coinbase_tx, regular_tx]
        with self.assertRaisesRegex(ValueError, "Input UTXO not found"):
            BlockValidator.check_transactions_and_get_fees(transactions, self.chain_state, block_height)

    def test_check_transactions_fails_on_invalid_signature(self):
        """测试交易列表，其中一个交易签名无效"""
        block_height = 10
        # 使用错误的私钥签名
        regular_tx = self._create_signed_tx(priv_key=self.priv_key2)

        coinbase_txin = TxIn.create_coinbase_txin(f"{block_height}:".encode())
        coinbase_tx = Transaction(1, [coinbase_txin], [], 0)
        
        transactions = [coinbase_tx, regular_tx]
        with self.assertRaisesRegex(ValueError, "Signature verification failed"):
            BlockValidator.check_transactions_and_get_fees(transactions, self.chain_state, block_height)

    def test_check_transactions_fails_on_coinbase_overspend(self):
        """测试Coinbase交易花费了超过 区块奖励+手续费 的总额"""
        block_height = 10
        fee = 200
        regular_tx = self._create_signed_tx(value=800) # 产生 200 手续费

        block_reward = BlockValidator.get_block_reward(block_height)
        # Coinbase 尝试花费 reward + fee + 1
        coinbase_txout = TxOut(block_reward + fee + 1, self.address2.encode())
        coinbase_txin = TxIn.create_coinbase_txin(f"{block_height}:".encode())
        coinbase_tx = Transaction(1, [coinbase_txin], [coinbase_txout], 0)

        transactions = [coinbase_tx, regular_tx]
        with self.assertRaisesRegex(ValueError, "Coinbase output value must equal block reward plus fees."):
            BlockValidator.check_transactions_and_get_fees(transactions, self.chain_state, block_height)

    def test_check_transactions_fails_on_wrong_coinbase_prefix(self):
        """测试Coinbase交易的解锁脚本前缀不正确"""
        block_height = 10
        wrong_height = 11
        regular_tx = self._create_signed_tx()

        # 使用错误的高度前缀
        coinbase_txin = TxIn.create_coinbase_txin(f"{wrong_height}:".encode())
        coinbase_tx = Transaction(1, [coinbase_txin], [], 0)

        transactions = [coinbase_tx, regular_tx]
        with self.assertRaisesRegex(ValueError, "Coinbase output value must equal block reward plus fees."):
            BlockValidator.check_transactions_and_get_fees(transactions, self.chain_state, block_height)

if __name__ == '__main__':
    unittest.main()