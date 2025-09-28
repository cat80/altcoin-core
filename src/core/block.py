from dataclasses import dataclass
from typing import List
import struct
import io
import time

from .block_header import BlockHeader
from .transaction import Transaction,TxIn,TxOut
from utils import MerkleTree,hash_data

# 定义一些常量
MAGIC_BYTES = b'\xab\xcd\xcd\xef' # 定义区块的头

@dataclass
class Block:
    """
    区块 (Block)
    包含了区块头和该区块打包的所有交易。
    """
    header: BlockHeader
    transactions: List[Transaction]

    @classmethod
    def create_new(cls, prev_block_hash: bytes, transactions: List[Transaction], bits: int) -> 'Block':
        """
        一个工厂方法，用于创建并打包一个全新的区块（挖矿前）。
        它会自动处理Coinbase交易和默克尔根的计算。
        """
        if not transactions:
            raise Exception("Transactions must not be null or empty")
        if not transactions[0].is_coinbase():
            raise Exception("The first transaction in a block must be a coinbase transaction.")

        # 1. 计算默克尔根
        tx_hashes = [tx.hash() for tx in transactions]
        merkle_root = MerkleTree(tx_hashes).root
        
        # 2. 创建区块头
        header = BlockHeader(
            version=1,
            prev_block_hash=prev_block_hash,
            merkle_root=merkle_root,
            timestamp=int(time.time()),
            bits=bits,
            nonce=0 # Nonce从0开始，由矿工去寻找
        )
        
        return cls(header, transactions)

    def hash(self) -> bytes:
        """计算并返回该区块的哈希。"""
        return self.header.hash()

    def serialize(self) -> bytes:
        """将完整的区块（头+交易）序列化为二进制。"""
        s = self.header.serialize()
        # 修正：这里应该是交易数量(定长int)，然后是所有交易的序列化数据
        s += struct.pack('<I', len(self.transactions))
        for tx in self.transactions:
            s += tx.serialize()
        return s

    @classmethod
    def deserialize(cls, stream: io.BytesIO) -> 'Block':
        """从二进制流中反序列化一个完整的区块。"""
        header = BlockHeader.deserialize(stream)
        tx_count, = struct.unpack('<I', stream.read(4))
        transactions = [Transaction.deserialize(stream) for _ in range(tx_count)]
        return cls(header, transactions)

    def to_raw_format(self) -> bytes:
        """
        打包成blk*.dat文件中的原始格式 (Magic + Size + Content)。
        """
        content = self.serialize()
        size = len(content)
        return MAGIC_BYTES + struct.pack('<I', size) + content