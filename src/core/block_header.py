import io
import struct
import time
import hashlib
from dataclasses import dataclass
from utils import *

@dataclass(frozen=True)
class BlockHeader:
    """
    区块头数据结构。
    使用@dataclass(frozen=True)使其成为一个不可变的、简洁的数据容器。
    """
    version: int
    prev_block_hash: bytes
    merkle_root: bytes
    timestamp: int
    bits: int
    nonce: int

    # 定义区块头的二进制结构。小端字节序, 总计80字节。
    FORMAT = '<I32s32sIII'

    def serialize(self) -> bytes:
        """将区块头序列化为80字节的二进制数据。"""
        return struct.pack(
            self.FORMAT,
            self.version,
            self.prev_block_hash,
            self.merkle_root,
            self.timestamp,
            self.bits,
            self.nonce
        )

    @classmethod
    def deserialize(cls, stream: io.BytesIO) -> 'BlockHeader':
        """从80字节的二进制数据中反序列化出区块头对象。"""

        version, prev_block_hash, merkle_root, timestamp, bits, nonce = struct.unpack(cls.FORMAT, stream.read(80))
        return cls(version, prev_block_hash, merkle_root, timestamp, bits, nonce)

    @classmethod
    def from_dict(cls, data: dict) -> 'BlockHeader':
        """从字典创建BlockHeader实例。"""
        return cls(
            version=data['version'],
            prev_block_hash=data['prev_block_hash'],
            merkle_root=data['merkle_root'],
            timestamp=data['timestamp'],
            bits=data['bits'],
            nonce=data['nonce']
        )

    def hash(self) -> bytes:
        """计算区块哈希（比特币风格的双重SHA256）。"""
        serialized_data = self.serialize()
        return hash_data(serialized_data)

