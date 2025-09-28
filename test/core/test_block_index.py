import unittest
import tempfile
import shutil
import os
import sys

# 添加src目录到Python路径中

from core.block_index import BlockIndex
from core.block_header import BlockHeader
from storage.sql_alchemy_wrapper import SQLAlchemyWrapper


class TestBlockIndex(unittest.TestCase):
    def setUp(self):
        """在每个测试方法之前创建临时目录和数据库实例"""
        # 创建临时目录用于测试
        self.temp_dir = tempfile.mkdtemp()
        self.db_path = os.path.join(self.temp_dir, 'test_database.db')
        # 创建一个临时的SQLAlchemyWrapper实例用于测试
        self.temp_db = SQLAlchemyWrapper(self.db_path)
        self.temp_db.create_all_tables()
        self.block_index = BlockIndex(self.temp_db)

    def tearDown(self):
        """在每个测试方法之后清理临时目录"""

        # 递归删除临时目录
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_add_header_and_get_header_info(self):
        """测试添加区块头和获取区块头信息"""
        # 创建一个区块头
        header = BlockHeader(
            version=1,
            prev_block_hash=b'\x00' * 32,
            merkle_root=b'\x01' * 32,
            timestamp=1234567890,
            bits=0x1d00ffff,
            nonce=12345
        )
        
        # 添加区块头到索引
        self.block_index.add_header(header, 0, 1000.0, 0, 100)
        
        # 获取区块头信息
        block_hash = header.hash()
        header_info = self.block_index.get_header_info(block_hash)
        
        # 验证返回的信息
        self.assertIsNotNone(header_info)
        self.assertEqual(header_info['block_hash'], block_hash)
        self.assertEqual(header_info['prev_block_hash'], b'\x00' * 32)
        self.assertEqual(header_info['merkle_root'], b'\x01' * 32)
        self.assertEqual(header_info['timestamp'], 1234567890)
        self.assertEqual(header_info['bits'], 0x1d00ffff)
        self.assertEqual(header_info['nonce'], 12345)
        self.assertEqual(header_info['height'], 0)
        self.assertEqual(header_info['total_work'], 1000.0)
        self.assertEqual(header_info['file_index'], 0)
        self.assertEqual(header_info['file_offset'], 100)

    def test_get_tip(self):
        """测试获取主链顶端区块"""
        # 创建两个区块头，第二个有更高的工作量
        header1 = BlockHeader(
            version=1,
            prev_block_hash=b'\x00' * 32,
            merkle_root=b'\x01' * 32,
            timestamp=1234567890,
            bits=0x1d00ffff,
            nonce=12345
        )
        
        header2 = BlockHeader(
            version=1,
            prev_block_hash=header1.hash(),
            merkle_root=b'\x02' * 32,
            timestamp=1234567891,
            bits=0x1d00ffff,
            nonce=12346
        )
        
        # 添加两个区块头，第二个有更高的工作量
        self.block_index.add_header(header1, 0, 1000.0, 0, 100)
        self.block_index.add_header(header2, 1, 2000.0, 0, 200)
        
        # 获取主链顶端
        tip = self.block_index.get_tip()
        
        # 验证返回的是工作量更高的区块
        self.assertIsNotNone(tip)
        self.assertEqual(tip['block_hash'], header2.hash())
        self.assertEqual(tip['height'], 1)
        self.assertEqual(tip['total_work'], 2000.0)

    def test_get_ancestor(self):
        """测试获取祖先区块"""
        # 创建一系列区块头形成链
        headers = []
        prev_hash = b'\x00' * 32
        
        for i in range(5):
            header = BlockHeader(
                version=1,
                prev_block_hash=prev_hash,
                merkle_root=bytes([i]) * 32,
                timestamp=1234567890 + i,
                bits=0x1d00ffff,
                nonce=12345 + i
            )
            headers.append(header)
            prev_hash = header.hash()
            
            # 添加区块头到索引
            self.block_index.add_header(header, i, float(1000 + i * 100), 0, 100 + i * 100)
        
        # 测试获取第3个区块（高度2）作为第5个区块（高度4）的祖先
        ancestor = self.block_index.get_ancestor(headers[4].hash(), 2)
        
        # 验证返回的祖先区块
        self.assertIsNotNone(ancestor)
        self.assertEqual(ancestor['block_hash'], headers[2].hash())
        self.assertEqual(ancestor['height'], 2)

    def test_get_ancestor_not_found(self):
        """测试获取不存在的祖先区块"""
        # 创建一个区块头
        header = BlockHeader(
            version=1,
            prev_block_hash=b'\x00' * 32,
            merkle_root=b'\x01' * 32,
            timestamp=1234567890,
            bits=0x1d00ffff,
            nonce=12345
        )
        
        # 添加区块头到索引
        self.block_index.add_header(header, 0, 1000.0, 0, 100)
        
        # 尝试获取一个不存在的祖先区块（高度太高）
        ancestor = self.block_index.get_ancestor(header.hash(), 5)
        
        # 应该返回None
        self.assertIsNone(ancestor)


if __name__ == '__main__':
    unittest.main()