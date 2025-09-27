import unittest
import time
import hashlib
from core.block_header import BlockHeader


class TestBlockHeader(unittest.TestCase):
    """
    针对BlockHeader类的单元测试套件。
    """

    def setUp(self):
        """
        在每个测试方法执行前运行，用于设置共享的测试数据。
        """
        self.sample_header = BlockHeader(
            version=1,
            prev_block_hash=b'\x00' * 32,
            merkle_root=hashlib.sha256(b'test data for setup').digest(),
            timestamp=int(time.time()),
            bits=0x1d00ffff,
            nonce=98765
        )

    def test_serialization_deserialization_roundtrip(self):
        """
        测试区块头的序列化和反序列化往返过程。
        """
        # 1. 操作 (Act) - 执行序列化和反序列化
        serialized_data = self.sample_header.serialize()
        deserialized_header = BlockHeader.deserialize(serialized_data)

        # 2. 断言 (Assert) - 验证结果是否符合预期
        self.assertEqual(len(serialized_data), 80, "Serialized header should be 80 bytes")
        # @dataclass自动生成的__eq__方法在这里同样有效
        self.assertEqual(self.sample_header, deserialized_header, "Deserialized header should be equal to the original")

    def test_hash_calculation(self):
        """
        测试区块哈希的计算，确保其格式和长度正确。
        """
        # 1. 操作 (Act)
        block_hash = self.sample_header.hash()

        # 2. 断言 (Assert)
        self.assertIsInstance(block_hash, bytes, "Hash should be a bytes object")
        self.assertEqual(len(block_hash), 32, "Hash should be 32 bytes long (SHA256)")
    def test_deserialization_error_on_wrong_length(self):
        """
        测试当输入数据长度不正确时，反序列化应抛出ValueError。
        """
        invalid_data = b'\x00' * 79  # 准备一段长度错误的数据
        # 使用assertRaises作为上下文管理器，来断言特定的异常是否被抛出
        with self.assertRaises(ValueError):
            BlockHeader.deserialize(invalid_data)


# --- 使测试文件可以直接运行的标准写法 ---
if __name__ == '__main__':
    unittest.main()