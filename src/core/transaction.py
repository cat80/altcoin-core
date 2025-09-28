from dataclasses import dataclass, field
from typing import List
import struct
import io

from utils.crypto import hash_data, verify_signature, ecdsa, CURVE


@dataclass(frozen=True)
class TxIn:
    """
    交易输入 (Transaction Input)
    引用一个之前的UTXO，并提供解锁脚本来证明所有权。
    """
    prev_tx_hash: bytes  # 被花费的UTXO所在的交易哈希 (32字节)
    prev_tx_out_index: int  # 被花费的UTXO在该交易输出列表中的索引 (4字节)
    unlocking_script: bytes  # 解锁脚本 (变长)

    def serialize(self) -> bytes:
        """序列化 TxIn：前置哈希(32字节) + 前置索引(4字节) + 脚本长度(4字节) + 脚本内容"""
        script_len = len(self.unlocking_script)
        # 这里的格式化字符串有点技巧：先打包固定部分，再拼接可变部分
        fixed_part = self.prev_tx_hash + struct.pack('<I', self.prev_tx_out_index)
        len_part = struct.pack('<I', script_len)
        return fixed_part + len_part + self.unlocking_script

    @classmethod
    def create_coinbase_txin(cls,unlocking_script:bytes):
        """
            根据解锁脚本创建一个coinbase in
        :param unlocking_script:
        :return:
        """
        return cls(prev_tx_out_index=0xffffffff,prev_tx_hash=b'\x00'*32,unlocking_script=unlocking_script)
    @classmethod
    def deserialize(cls, stream: io.BytesIO) -> 'TxIn':
        """从字节流中反序列化 TxIn"""
        prev_tx_hash = stream.read(32)
        prev_tx_out_index, script_len = struct.unpack('<II', stream.read(8))
        unlocking_script = stream.read(script_len)
        return cls(prev_tx_hash, prev_tx_out_index, unlocking_script)


@dataclass(frozen=True)
class TxOut:
    """
    交易输出 (Transaction Output)
    定义了一笔钱的归属和金额。每个TxOut都是一个潜在的UTXO。
    """
    value: int  # 金额 (用最小单位表示，8字节)
    locking_script: bytes  # 锁定脚本 (变长)

    def serialize(self) -> bytes:
        """序列化 TxOut：金额(8字节) + 脚本长度(4字节) + 脚本内容"""
        script_len = len(self.locking_script)
        return struct.pack(f'<QI{script_len}s', self.value, script_len, self.locking_script)

    @classmethod
    def deserialize(cls, stream: io.BytesIO) -> 'TxOut':
        """从字节流中反序列化 TxOut"""
        # 读取 8字节金额 + 4字节脚本长度
        value, script_len = struct.unpack('<QI', stream.read(12))
        locking_script = stream.read(script_len)
        return cls(value, locking_script)


@dataclass(frozen=True)
class Transaction:
    """
    交易 (Transaction)
    包含了版本、输入列表、输出列表和锁定时间。
    """
    version: int
    tx_ins: List[TxIn]
    tx_outs: List[TxOut]
    lock_time: int
    op_return_data: bytes = field(default=None)

    def hash(self) -> bytes:
        """计算并返回这笔交易的哈希ID (TxID)"""
        return hash_data(self.serialize(for_signing=True))

    def serialize(self, for_signing: bool = False) -> bytes:
        """
        将整个交易序列化为二进制字节流。
        该方法同时处理常规序列化和为签名构建数据摘要两种情况。
        """
        s = struct.pack('<I', self.version)

        s += struct.pack('<I', len(self.tx_ins))
        for i, tx_in in enumerate(self.tx_ins):
            if for_signing:
                temp_in = TxIn(tx_in.prev_tx_hash, tx_in.prev_tx_out_index, b'')
                s += temp_in.serialize()
            else:
                # 常规序列化
                s += tx_in.serialize()

        s += struct.pack('<I', len(self.tx_outs))
        for tx_out in self.tx_outs:
            s += tx_out.serialize()

        s += struct.pack('<I', self.lock_time)

        if self.op_return_data:
            s += struct.pack('<I', len(self.op_return_data))
            s += self.op_return_data
        else:
            # 修正，如果字段为空则记录为长度为零
            s += struct.pack('<I', 0)

        return s

    @classmethod
    def deserialize(cls, stream: io.BytesIO) -> 'Transaction':
        """从二进制字节流中反序列化出交易对象。"""

        version, = struct.unpack('<I', stream.read(4))
        tx_in_count, = struct.unpack('<I', stream.read(4))
        tx_ins = [TxIn.deserialize(stream) for _ in range(tx_in_count)]

        tx_out_count, = struct.unpack('<I', stream.read(4))
        tx_outs = [TxOut.deserialize(stream) for _ in range(tx_out_count)]
        locktime, = struct.unpack('<I', stream.read(4))
        op_return_data = None
        # 检查流中是否还有剩余数据（即op_return_data）
        data_len, = struct.unpack('<I', stream.read(4))
        if data_len:
            op_return_data = stream.read(data_len)

        return cls(version, tx_ins, tx_outs, locktime, op_return_data)

    def is_coinbase(self) -> bool:
        """
        判断这笔交易是否为Coinbase交易。
        """
        return (len(self.tx_ins) == 1 and
                self.tx_ins[0].prev_tx_hash == b'\x00' * 32 and
                self.tx_ins[0].prev_tx_out_index == 0xFFFFFFFF)

    @classmethod
    def create_coinbase_transaction(self,tx_outs, unlocking_script=None):
        tx_inds = TxIn(prev_tx_hash=b'\x00' * 32,prev_tx_out_index= 0xFFFFFFFF)

    def verify_signature(self) -> bool:
        """
        验证当前交易的签名是否有效。
        :return: 如果当前交易的签名有效，返回True。
        """
        # 如果是coinbase认定签名有效
        if self.is_coinbase():
            return True

        hash_for_signing = self.serialize(for_signing=True)

        for input_index,tx_in in enumerate(self.tx_ins) :
            # 从解锁脚本中解析公钥和签名
            if len(tx_in.unlocking_script) != 128:
                raise Exception(f'tx_index:{input_index},unlocking script len not equal 128,actual:{len(tx_in.unlocking_script)} ')
            signature = tx_in.unlocking_script[:64]
            public_key_bytes = tx_in.unlocking_script[64:]
            public_key = ecdsa.VerifyingKey.from_string(public_key_bytes, curve=CURVE)
            if not verify_signature(hash_for_signing, signature,public_key ):
                return False
        return True