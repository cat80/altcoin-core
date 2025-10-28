"""
block_storage.py
负责将完整的区块数据写入磁盘文件 (blk*****.dat) 并从中读取。
这个模块被封装成一个类，以管理数据目录的状态。
"""
import logging
import os
import io
import struct
from typing import Tuple

from .block import Block
from config import MAGIC_BYTES
# 每个区块文件的最大大小 (例如: 128MB)
MAX_FILE_SIZE = 128 * 1024 * 1024

log = logging.getLogger(__name__)
class BlockStorage:
    """
    管理区块数据在磁盘上的读写。
    """
    def __init__(self, data_dir: str):
        self.data_dir = data_dir
        os.makedirs(self.data_dir, exist_ok=True)

    def _get_block_file_path(self, file_index: int) -> str:
        """根据文件索引生成 blk*****.dat 文件路径。"""
        return os.path.join(self.data_dir, f'blk{file_index:05d}.dat')

    def _find_last_block_file(self) -> Tuple[int, int]:
        """
        查找最后一个区块文件及其大小。
        返回 (last_file_index, last_file_size)。
        如果没有任何文件，则返回 (0, 0)。
        """
        last_index = -1
        for filename in os.listdir(self.data_dir):
            if filename.startswith('blk') and filename.endswith('.dat'):
                try:
                    index = int(filename[3:-4])
                    if index > last_index:
                        last_index = index
                except ValueError:
                    continue
        
        if last_index == -1:
            return 0, 0
        
        last_file_path = self._get_block_file_path(last_index)
        return last_index, os.path.getsize(last_file_path)

    def write_block(self, block: Block) -> Tuple[int, int]:
        """
        将一个区块写入到磁盘。
        如果当前文件大小超过限制，会自动创建新文件。
        返回存储位置: (file_index, offset)。
        """
        file_index, file_size = self._find_last_block_file()
        # 边界处理问题
        if file_size >= MAX_FILE_SIZE:
            file_index += 1
            file_size = 0
            
        file_path = self._get_block_file_path(file_index)
        offset = file_size
        
        raw_block_data = block.to_raw_format()
        
        with open(file_path, 'ab') as f:
            f.write(raw_block_data)
            
        return file_index, offset

    def read_block(self, file_index: int, offset: int) -> Block:
        """
        从磁盘的指定位置读取一个完整的区块。
        """
        file_path = self._get_block_file_path(file_index)
        
        with open(file_path, 'rb') as f:
            f.seek(offset)
            
            # 1. 读取 Magic 和 Size
            magic = f.read(4)
            if not magic:
                raise EOFError("Reached end of file unexpectedly while reading magic bytes.")
            if magic != MAGIC_BYTES:
                raise ValueError(f"Invalid block magic bytes. Expected {MAGIC_BYTES.hex()}, got {magic.hex()}")
                
            size_bytes = f.read(4)
            if len(size_bytes) < 4:
                raise EOFError("Reached end of file unexpectedly while reading size.")
            size, = struct.unpack('<I', size_bytes)
            
            # 2. 读取并反序列化区块内容
            block_data = f.read(size)
            if len(block_data) < size:
                 raise EOFError("Reached end of file unexpectedly while reading block data.")

            return Block.deserialize(io.BytesIO(block_data))