import unittest
import sys
import os
import tempfile
import shutil


from storage.rocksdb_wrapper import RocksDBWrapper
from config import config

class TestRocksDBWrapper(unittest.TestCase):
    
    def setUp(self):
        """在每个测试方法之前创建临时目录和数据库实例"""

        self.db_path = config.rocksdb_dir
        self.db = RocksDBWrapper(self.db_path)
    
    def tearDown(self):
        """在每个测试方法之后清理临时目录"""
        self.db.close()
        # 递归删除临时目录
    
    def test_init_and_put_get(self):
        """测试数据库初始化以及基本的put和get操作"""
        # 测试数据
        key = b'test_key'
        value = b'test_value'
        
        # 放入数据
        self.db.put(key, value)
        
        # 获取数据
        retrieved_value = self.db.get(key)
        
        # 验证数据正确性
        self.assertEqual(retrieved_value, value)
    
    def test_get_nonexistent_key(self):
        """测试获取不存在的键"""
        key = b'nonexistent_key'
        value = self.db.get(key)
        self.assertIsNone(value)
    
    def test_delete_key(self):
        """测试删除键值对"""
        # 先放入数据
        key = b'test_key'
        value = b'test_value'
        self.db.put(key, value)
        
        # 确认数据存在
        self.assertEqual(self.db.get(key), value)
        
        # 删除数据
        self.db.delete(key)
        
        # 确认数据已被删除
        self.assertIsNone(self.db.get(key))
    
    def test_new_batch(self):
        """测试创建批处理对象"""
        batch = self.db.new_batch()
        self.assertIsNotNone(batch)
    
    def test_write_batch(self):
        """测试批量写入数据"""
        # 创建批处理对象

        batch = self.db.new_batch()
        
        # 添加多个键值对到批处理中
        batch.add(b'key1', b'value1')
        batch.add(b'key2', b'value2')
        batch.add(b'key3', b'value3')
        
        # 执行批处理写入
        self.db.write_batch(batch)
        
        # 验证数据已写入
        self.assertEqual(self.db.get(b'key1'), b'value1')
        self.assertEqual(self.db.get(b'key2'), b'value2')
        self.assertEqual(self.db.get(b'key3'), b'value3')
    
    def test_write_batch_bytes(self):
        """测试write_batch_bytes方法"""
        # 准备测试数据
        datas = [
            (b'key1', b'value1'),
            (b'key2', b'value2'),
            (b'key3', b'value3')
        ]
        
        # 执行批量写入
        self.db.write_batch_bytes(datas)
        
        # 验证数据已写入
        self.assertEqual(self.db.get(b'key1'), b'value1')
        self.assertEqual(self.db.get(b'key2'), b'value2')
        self.assertEqual(self.db.get(b'key3'), b'value3')


if __name__ == '__main__':
    unittest.main()