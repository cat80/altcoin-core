import unittest
import tempfile
import shutil
import os
import sys

# 添加src目录到Python路径中
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from core.blockchain import Blockchain
from core.block import Block
from core.block_header import BlockHeader
from core.transaction import Transaction, TxIn, TxOut


class TestBlockchain(unittest.TestCase):
    def setUp(self):
        """在每个测试方法之前创建临时目录"""
        self.temp_dir = tempfile.mkdtemp()
        self.blockchain = Blockchain(self.temp_dir)

    def tearDown(self):
        """在每个测试方法之后清理临时目录"""
        self.blockchain.close()
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_init_genesis_block(self):
        """测试创世区块初始化"""
        # 验证创世区块已创建
        tip = self.blockchain.get_best_tip()
        self.assertIsNotNone(tip)
        self.assertEqual(tip['height'], 0)
        
        # 验证创世区块信息
        genesis_block_info = self.blockchain.block_index.get_header_info(tip['block_hash'])
        self.assertIsNotNone(genesis_block_info)
        self.assertEqual(genesis_block_info['height'], 0)

    def test_get_best_tip(self):
        """测试获取最佳区块头"""
        tip = self.blockchain.get_best_tip()
        self.assertIsNotNone(tip)
        self.assertEqual(tip['height'], 0)
        
        # 验证tip包含必要的字段
        self.assertIn('block_hash', tip)
        self.assertIn('height', tip)
        self.assertIn('total_work', tip)

    def test_add_block_orphan(self):
        """测试添加孤儿区块"""
        # 创建一个孤儿区块（父区块哈希是随机的）
        header = BlockHeader(
            version=1,
            prev_block_hash=b'\x01' * 32,  # 不存在的父区块
            merkle_root=b'\x02' * 32,
            timestamp=1234567890,
            bits=0x1d00ffff,
            nonce=12345
        )
        
        coinbase_tx = Transaction(
            version=1,
            tx_ins=[TxIn.create_coinbase_txin(b"orphan")],
            tx_outs=[TxOut(5000000000, b"test_script")],
            lock_time=0
        )
        
        orphan_block = Block(header, [coinbase_tx])
        
        # 尝试添加孤儿区块应该失败
        result = self.blockchain.add_block(orphan_block)
        self.assertFalse(result)
        
        # 验证链状态没有改变
        tip = self.blockchain.get_best_tip()
        self.assertEqual(tip['height'], 0)

    def test_add_block_invalid_pow(self):
        """测试添加PoW无效的区块"""
        # 获取当前最佳区块作为父区块
        prev_tip = self.blockchain.get_best_tip()
        prev_block_hash = prev_tip['block_hash']
        
        # 创建一个区块但不进行挖矿（无效的PoW）
        header = BlockHeader(
            version=1,
            prev_block_hash=prev_block_hash,
            merkle_root=b'\x01' * 32,
            timestamp=1234567890,
            bits=0x1d00ffff,
            nonce=0  # 未挖矿的nonce
        )
        
        coinbase_tx = Transaction(
            version=1,
            tx_ins=[TxIn.create_coinbase_txin(b"invalid_pow")],
            tx_outs=[TxOut(5000000000, b"test_script")],
            lock_time=0
        )
        
        invalid_block = Block(header, [coinbase_tx])
        
        # 尝试添加无效PoW区块应该失败
        result = self.blockchain.add_block(invalid_block)
        self.assertFalse(result)
        
        # 验证链状态没有改变
        tip = self.blockchain.get_best_tip()
        self.assertEqual(tip['height'], 0)


if __name__ == '__main__':
    unittest.main()