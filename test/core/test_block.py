import unittest
import sys
import os
import io
import time
from unittest.mock import patch


from core.block import Block, MAGIC_BYTES
from core.block_header import BlockHeader
from core.transaction import Transaction, TxIn, TxOut


class TestBlock(unittest.TestCase):

    def setUp(self):
        """测试前的准备工作"""
        # 创建一些测试交易
        txin1 = TxIn(
            prev_tx_hash=b'\x00' * 32,
            prev_tx_out_index=0,
            unlocking_script=b'test_unlock_script_1'
        )
        txout1 = TxOut(
            value=1000,
            locking_script=b'test_lock_script_1'
        )
        self.test_transaction = Transaction(
            version=1,
            tx_ins=[txin1],
            tx_outs=[txout1],
            lock_time=0
        )

        # 创建coinbase交易
        coinbase_txin = TxIn.create_coinbase_txin(b'Coinbase Data - AltCoin Mined!')
        coinbase_txout = TxOut(
            value=5000,
            locking_script=b'\x00' * 20
        )
        self.coinbase_transaction = Transaction(
            version=1,
            tx_ins=[coinbase_txin],
            tx_outs=[coinbase_txout],
            lock_time=0
        )

    def test_create_new_block(self):
        """测试创建新区块"""
        prev_block_hash = b'\x00' * 32
        bits = 0x1d00ffff
        transactions = [self.test_transaction]
        transactions.insert(0,self.coinbase_transaction)
        # 使用patch来模拟time.time()的返回值，使测试结果可预测
        with patch('time.time', return_value=1234567890):
            block = Block.create_new(prev_block_hash, transactions, bits)
        
        # 验证区块头属性
        self.assertEqual(block.header.version, 1)
        self.assertEqual(block.header.prev_block_hash, prev_block_hash)
        self.assertEqual(block.header.bits, bits)
        self.assertEqual(block.header.nonce, 0)
        self.assertEqual(block.header.timestamp, 1234567890)
        
        # 验证交易列表
        self.assertEqual(len(block.transactions), 2)  # 应该包含coinbase交易和测试交易
        self.assertTrue(block.transactions[0].is_coinbase())
        self.assertEqual(block.transactions[1], self.test_transaction)

    def test_create_new_block_without_transactions(self):
        """测试创建没有交易的区块应该抛出异常"""
        prev_block_hash = b'\x00' * 32
        bits = 0x1d00ffff
        transactions = []
        
        with self.assertRaises(Exception) as context:
            Block.create_new(prev_block_hash, transactions, bits)
            
        self.assertTrue("Transactions must not be null or empty" in str(context.exception))

    def test_hash(self):
        """测试区块哈希计算"""
        # 创建一个简单的区块头
        header = BlockHeader(
            version=1,
            prev_block_hash=b'\x00' * 32,
            merkle_root=b'\x00' * 32,
            timestamp=1234567890,
            bits=0x1d00ffff,
            nonce=12345
        )
        
        block = Block(header=header, transactions=[])
        # 区块哈希应该等于区块头哈希
        self.assertEqual(block.hash(), header.hash())

    def test_serialize_deserialize(self):
        """测试区块序列化和反序列化"""
        # 创建一个区块
        header = BlockHeader(
            version=1,
            prev_block_hash=b'\x01' * 32,
            merkle_root=b'\x02' * 32,
            timestamp=1234567890,
            bits=0x1d00ffff,
            nonce=12345
        )
        
        block = Block(header=header, transactions=[self.coinbase_transaction, self.test_transaction])
        
        # 序列化
        serialized_data = block.serialize()
        
        # 反序列化
        stream = io.BytesIO(serialized_data)
        deserialized_block = Block.deserialize(stream)
        
        # 验证反序列化后的区块与原区块相同
        self.assertEqual(deserialized_block.header.version, header.version)
        self.assertEqual(deserialized_block.header.prev_block_hash, header.prev_block_hash)
        self.assertEqual(deserialized_block.header.merkle_root, header.merkle_root)
        self.assertEqual(deserialized_block.header.timestamp, header.timestamp)
        self.assertEqual(deserialized_block.header.bits, header.bits)
        self.assertEqual(deserialized_block.header.nonce, header.nonce)
        
        self.assertEqual(len(deserialized_block.transactions), len(block.transactions))
        for i in range(len(block.transactions)):
            self.assertEqual(deserialized_block.transactions[i].hash(), block.transactions[i].hash())

    def test_to_raw_format(self):
        """测试区块转换为原始格式"""
        # 创建一个区块
        header = BlockHeader(
            version=1,
            prev_block_hash=b'\x01' * 32,
            merkle_root=b'\x02' * 32,
            timestamp=1234567890,
            bits=0x1d00ffff,
            nonce=12345
        )
        
        block = Block(header=header, transactions=[self.coinbase_transaction])
        
        # 转换为原始格式
        raw_data = block.to_raw_format()
        
        # 检查是否包含magic bytes
        self.assertEqual(raw_data[:4], MAGIC_BYTES)
        
        # 检查大小字段
        content_size = len(block.serialize())
        size_field = raw_data[4:8]
        size_from_field = int.from_bytes(size_field, byteorder='little')
        self.assertEqual(size_from_field, content_size)
        
        # 检查内容
        content = raw_data[8:]
        self.assertEqual(content, block.serialize())


if __name__ == '__main__':
    unittest.main()