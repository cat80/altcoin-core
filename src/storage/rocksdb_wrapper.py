import os
import rocksdbpy as rocksdb
from typing import List, Iterator, Tuple

__global_rocksdb_dict = {}

class RocksDBWrapper:
    """对RocksDB操作的简单封装，确保数据库连接的正确管理。"""

    def __init__(self, db_path):
        os.makedirs(db_path, exist_ok=True)
        opts = rocksdb.Option()
        opts.create_if_missing (  True)
        self.db :rocksdb.RocksDB = rocksdb.open(db_path, opts)

    def get(self, key):
        return self.db.get(key)

    def put(self, key, value):
        self.db.set(key, value)

    def delete(self, key):
        self.db.delete(key)

    def close(self):
        # 实际应用中可能不需要手动关闭，取决于应用生命周期
        pass

    def new_batch(self):
        """返回一个批处理对象，用于原子性地执行多个写操作。"""
        return rocksdb.WriteBatch()

    def write_batch_bytes(self,datas:List):
        """"
            批量增加二进制数据列表
        """
        write_batch = self.new_batch()
        for key,value in datas:
            write_batch.add(key,value)
        self.write_batch(write_batch)

    def write_batch(self, batch):
        self.db.write(batch)

    def iter_keys(self) -> Iterator[bytes]:
        """
        迭代所有键
        """
        # 使用rocksdbpy的正确迭代方法
        try:
            it = self.db.iterator()
            it.seek_to_first()
            try:
                while it.valid():
                    yield it.key()
                    it.next()
            finally:
                it.close()
        except AttributeError:
            # 如果没有iterator()方法，尝试其他方法
            raise NotImplementedError("当前rocksdbpy版本不支持键迭代功能")

    def iter_items(self) -> Iterator[Tuple[bytes, bytes]]:
        """
        迭代所有键值对
        """
        # 使用rocksdbpy的正确迭代方法
        try:
            it = self.db.iterator()
            it.seek_to_first()
            try:
                while it.valid():
                    yield (it.key(), it.value())
                    it.next()
            finally:
                it.close()
        except AttributeError:
            # 如果没有iterator()方法，尝试其他方法
            raise NotImplementedError("当前rocksdbpy版本不支持键值对迭代功能")