import logging
import unittest
import sys
import os
import tempfile
import shutil
from sqlalchemy.orm import Session
log = logging.getLogger(__name__)
from storage.sql_alchemy_wrapper import SQLAlchemyWrapper, BlockHeaderModel


class TestSQLAlchemyWrapper(unittest.TestCase):
    
    def setUp(self):
        """在每个测试方法之前创建临时目录和数据库实例"""
        # 创建临时目录用于测试
        self.temp_dir = tempfile.mkdtemp()
        self.db_path =     self.temp_dir + "/index.db"
        self.db = SQLAlchemyWrapper(self.db_path)
        self.db.create_all_tables()
        log.debug(f'use db_path:{self.db_path}')
    def tearDown(self):
        """在每个测试方法之后清理临时目录"""
        # 递归删除临时目录
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def test_init(self):
        """测试数据库初始化"""
        # 确保数据库实例已正确创建
        self.assertIsNotNone(self.db.engine)
        self.assertIsNotNone(self.db.SessionLocal)
        self.assertIsNotNone(self.db.Base)
    
    def test_get_session(self):
        """测试获取数据库会话"""
        with self.db.get_session() as session:
            self.assertIsNotNone(session)

    
    def test_create_all_tables(self):
        """测试创建所有表"""
        # 调用创建表的方法
        self.db.create_all_tables()
        
        # 验证数据库文件已创建
        self.assertTrue(os.path.exists(self.db_path))

    def test_block_header_model_creation(self):
        """测试BlockHeaderModel的创建和基本属性"""
        # 创建表
        self.db.create_all_tables()
        
        # 创建会话
        session: Session = self.db.get_session()
        
        try:
            # 创建一个模拟的区块头数据
            block_hash = b'\x01' * 32
            prev_block_hash = b'\x01' * 32
            merkle_root = b'\x02' * 32
            
            header_model = BlockHeaderModel(
                block_hash=block_hash,
                prev_block_hash=prev_block_hash,
                merkle_root=merkle_root,
                timestamp=1234567890,
                bits=0x1d00ffff,
                nonce=12345,
                height=100,
                total_work=1000.5,
                status=1,
                file_index=0,
                file_offset=1000
            )
            # 新增新删除同一个hash的避免重复
            session.query(BlockHeaderModel).filter(BlockHeaderModel.block_hash.in_([block_hash])).delete(synchronize_session=False)
            session.commit()

            # 添加到会话并提交
            session.add(header_model)
            session.commit()
            
            # 查询刚刚插入的数据
            queried_header = session.query(BlockHeaderModel).filter_by(block_hash=block_hash).first()
            
            # 验证数据是否正确保存
            self.assertIsNotNone(queried_header)
            self.assertEqual(queried_header.block_hash, block_hash)
            self.assertEqual(queried_header.prev_block_hash, prev_block_hash)
            self.assertEqual(queried_header.merkle_root, merkle_root)
            self.assertEqual(queried_header.timestamp, 1234567890)
            self.assertEqual(queried_header.bits, 0x1d00ffff)
            self.assertEqual(queried_header.nonce, 12345)
            self.assertEqual(queried_header.height, 100)
            self.assertEqual(queried_header.total_work, 1000.5)
            self.assertEqual(queried_header.status, 1)
            self.assertEqual(queried_header.file_index, 0)
            self.assertEqual(queried_header.file_offset, 1000)

        #
            session.query(BlockHeaderModel).filter(BlockHeaderModel.block_hash.in_([block_hash])).delete(
                synchronize_session=False)
            session.commit()
            self.assertIsNone(  session.query(BlockHeaderModel).filter_by(block_hash=block_hash).first())
        finally:
            session.close()
    
    def test_block_header_model_to_dict(self):
        """测试BlockHeaderModel的to_dict方法"""
        # 创建表
        self.db.create_all_tables()
        
        # 创建会话
        session: Session = self.db.get_session()
        
        try:
            # 创建一个模拟的区块头数据
            block_hash = b'\x00' * 32
            prev_block_hash = b'\x01' * 32
            merkle_root = b'\x02' * 32
            
            header_model = BlockHeaderModel(
                block_hash=block_hash,
                prev_block_hash=prev_block_hash,
                merkle_root=merkle_root,
                timestamp=1234567890,
                bits=0x1d00ffff,
                nonce=12345,
                height=100,
                total_work=1000.5,
                status=1,
                file_index=0,
                file_offset=1000
            )
            
            # 转换为字典
            header_dict = header_model.to_dict()
            
            # 验证字典包含所有字段
            expected_keys = {
                'block_hash', 'prev_block_hash', 'merkle_root', 'timestamp',
                'bits', 'nonce', 'height', 'total_work', 'status',
                'file_index', 'file_offset'
            }
            
            self.assertEqual(set(header_dict.keys()), expected_keys)
            self.assertEqual(header_dict['block_hash'], block_hash)
            self.assertEqual(header_dict['prev_block_hash'], prev_block_hash)
            self.assertEqual(header_dict['merkle_root'], merkle_root)
            self.assertEqual(header_dict['timestamp'], 1234567890)
            self.assertEqual(header_dict['bits'], 0x1d00ffff)
            self.assertEqual(header_dict['nonce'], 12345)
            self.assertEqual(header_dict['height'], 100)
            self.assertEqual(header_dict['total_work'], 1000.5)
            self.assertEqual(header_dict['status'], 1)
            self.assertEqual(header_dict['file_index'], 0)
            self.assertEqual(header_dict['file_offset'], 1000)
            
        finally:
            session.close()


if __name__ == '__main__':
    unittest.main()