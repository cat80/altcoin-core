import logging
import unittest
import tempfile
import shutil
import os
import sys
import struct

# 添加src目录到Python路径中
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from core.block_storage import BlockStorage
from core.block import Block
from core.block_header import BlockHeader
from core.transaction import Transaction, TxIn, TxOut
from config import MAGIC_BYTES
log = logging.getLogger(__name__)
class TestBlockStorage(unittest.TestCase):
    def setUp(self):
        """在每个测试方法之前创建临时目录"""
        self.temp_dir = tempfile.mkdtemp()
        self.block_storage = BlockStorage(self.temp_dir)
        log.debug(f'test {__name__} temp_dir is:{self.temp_dir}')
    def tearDown(self):
        """在每个测试方法之后清理临时目录"""
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_write_and_read_block(self):
        """测试写入和读取区块"""
        # 创建一个测试区块
        header = BlockHeader(
            version=1,
            prev_block_hash=b'\x00' * 32,
            merkle_root=b'\x01' * 32,
            timestamp=1234567890,
            bits=0x1d00ffff,
            nonce=12345
        )
        
        # 创建一个coinbase交易
        coinbase_tx = Transaction(
            version=1,
            tx_ins=[TxIn.create_coinbase_txin(b"test")],
            tx_outs=[TxOut(5000000000, b"test_script")],
            lock_time=0
        )
        
        block = Block(header, [coinbase_tx])
        
        # 写入区块
        file_index, offset = self.block_storage.write_block(block)
        
        # 读取区块
        read_block = self.block_storage.read_block(file_index, offset)
        
        # 验证读取的区块与原始区块相同
        self.assertEqual(read_block.header.version, header.version)
        self.assertEqual(read_block.header.prev_block_hash, header.prev_block_hash)
        self.assertEqual(read_block.header.merkle_root, header.merkle_root)
        self.assertEqual(read_block.header.timestamp, header.timestamp)
        self.assertEqual(read_block.header.bits, header.bits)
        self.assertEqual(read_block.header.nonce, header.nonce)
        
        # 验证交易
        self.assertEqual(len(read_block.transactions), 1)
        self.assertTrue(read_block.transactions[0].is_coinbase())
        self.assertEqual(read_block.transactions[0].tx_outs[0].value, 5000000000)

    def test_multiple_blocks_in_same_file(self):
        """测试在同一文件中写入多个区块"""
        blocks = []
        
        # 创建多个测试区块
        for i in range(3):
            header = BlockHeader(
                version=1,
                prev_block_hash=bytes([i]) * 32,
                merkle_root=bytes([i+1]) * 32,
                timestamp=1234567890 + i,
                bits=0x1d00ffff,
                nonce=12345 + i
            )
            
            coinbase_tx = Transaction(
                version=1,
                tx_ins=[TxIn.create_coinbase_txin(f"test_{i}".encode())],
                tx_outs=[TxOut(5000000000, f"test_script_{i}".encode())],
                lock_time=0
            )
            
            block = Block(header, [coinbase_tx])
            blocks.append(block)
        
        # 写入所有区块
        locations = []
        for block in blocks:
            file_index, offset = self.block_storage.write_block(block)
            locations.append((file_index, offset))
        
        # 验证所有区块都在同一个文件中
        for file_index, _ in locations:
            self.assertEqual(file_index, 0)
        
        # 读取并验证所有区块
        for i, (file_index, offset) in enumerate(locations):
            read_block = self.block_storage.read_block(file_index, offset)
            self.assertEqual(read_block.header.prev_block_hash, blocks[i].header.prev_block_hash)
            self.assertEqual(read_block.header.merkle_root, blocks[i].header.merkle_root)

    def test_new_file_creation_when_max_size_exceeded(self):
        """测试当文件大小超过限制时创建新文件"""
        # 创建一个小的区块用于测试
        header = BlockHeader(
            version=1,
            prev_block_hash=b'\x00' * 32,
            merkle_root=b'\x01' * 32,
            timestamp=1234567890,
            bits=0x1d00ffff,
            nonce=12345
        )
        
        coinbase_tx = Transaction(
            version=1,
            tx_ins=[TxIn.create_coinbase_txin(b"test")],
            tx_outs=[TxOut(5000000000, b"test_script")],
            lock_time=0
        )
        
        block = Block(header, [coinbase_tx])
        
        # 获取序列化后的区块大小
        raw_block_data = block.to_raw_format()
        block_size = len(raw_block_data)
        
        # 设置一个很小的文件大小限制来测试新文件创建
        # 注意：这会修改模块级常量，仅在测试中使用
        import core.block_storage
        original_max_file_size = core.block_storage.MAX_FILE_SIZE
        core.block_storage.MAX_FILE_SIZE = block_size  # 设置为刚好能容纳一个区块的大小
        
        try:
            # 写入第一个区块
            file_index1, offset1 = self.block_storage.write_block(block)
            
            # 写入第二个区块，应该创建新文件
            file_index2, offset2 = self.block_storage.write_block(block)
            
            # 验证第二个区块被写入新文件
            self.assertEqual(file_index1, 0)
            self.assertEqual(offset1, 0)
            self.assertEqual(file_index2, 1)
            self.assertEqual(offset2, 0)
        finally:
            # 恢复原始的MAX_FILE_SIZE值
            core.block_storage.MAX_FILE_SIZE = original_max_file_size

    def test_read_block_with_invalid_magic_bytes(self):
        """测试读取具有无效magic字节的区块"""
        # 创建一个区块并写入
        header = BlockHeader(
            version=1,
            prev_block_hash=b'\x00' * 32,
            merkle_root=b'\x01' * 32,
            timestamp=1234567890,
            bits=0x1d00ffff,
            nonce=12345
        )
        
        coinbase_tx = Transaction(
            version=1,
            tx_ins=[TxIn.create_coinbase_txin(b"test")],
            tx_outs=[TxOut(5000000000, b"test_script")],
            lock_time=0
        )
        
        block = Block(header, [coinbase_tx])
        file_index, offset = self.block_storage.write_block(block)
        
        # 手动修改文件中的magic字节使其无效
        file_path = self.block_storage._get_block_file_path(file_index)
        with open(file_path, 'r+b') as f:
            f.seek(offset)
            f.write(b'\x00\x00\x00\x00')  # 写入无效的magic字节
        
        # 尝试读取区块应该抛出ValueError
        with self.assertRaises(ValueError):
            self.block_storage.read_block(file_index, offset)

    def test_find_last_block_file(self):
        """测试查找最后一个区块文件"""
        # 初始状态下应该返回(0, 0)
        last_index, last_size = self.block_storage._find_last_block_file()
        self.assertEqual(last_index, 0)
        self.assertEqual(last_size, 0)
        
        # 创建一个区块
        header = BlockHeader(
            version=1,
            prev_block_hash=b'\x00' * 32,
            merkle_root=b'\x01' * 32,
            timestamp=1234567890,
            bits=0x1d00ffff,
            nonce=12345
        )
        
        coinbase_tx = Transaction(
            version=1,
            tx_ins=[TxIn.create_coinbase_txin(b"test")],
            tx_outs=[TxOut(5000000000, b"test_script")],
            lock_time=0
        )
        
        block = Block(header, [coinbase_tx])
        
        # 写入区块
        file_index, _ = self.block_storage.write_block(block)
        
        # 现在应该能找到文件
        last_index, last_size = self.block_storage._find_last_block_file()
        self.assertEqual(last_index, 0)
        self.assertGreater(last_size, 0)


if __name__ == '__main__':
    unittest.main()