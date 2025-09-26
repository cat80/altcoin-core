import unittest
import ecdsa
from utils import *

class TestCrypto(unittest.TestCase):
    """
    针对crypto.py工具集的单元测试套件。
    """

    def test_hash_data(self):
        """
        测试hash_data函数是否能正确生成确定性的32字节哈希。
        """
        data1 = b"hello world"
        data2 = b"hello world"
        data3 = b"goodbye world"

        print(len('0xa31873E54B06454B68E58DCda7806AEce3AF91fD'))
        # 0xa31873E54B06454B68E58DCda7806AEce3AF91fD
        # bc62d4b80d9e36da29c16c5d4d9f11731f36052c72401a76c23c0fb5a9b74423
        hash1 = hash_data(data1)
        hash2 = hash_data(data2)
        hash3 = hash_data(data3)
        print(hash1)
        hexhash = hash1.hex()
        print(hexhash)
        print(bytes.fromhex(hexhash))

        self.assertIsInstance(hash1, bytes, "哈希结果应为bytes类型")
        self.assertEqual(len(hash1), 32, "哈希结果应为32字节")
        self.assertEqual(hash1, hash2, "相同数据的哈希结果应相同")
        self.assertNotEqual(hash1, hash3, "不同数据的哈希结果应不同")

    def test_generate_keypair(self):
        """
        测试generate_keypair函数能否生成有效的ECDSA密钥对。
        """
        private_key, public_key = generate_keypair()

        self.assertIsInstance(private_key, ecdsa.SigningKey, "私钥应为SigningKey类型")
        self.assertIsInstance(public_key, ecdsa.VerifyingKey, "公钥应为VerifyingKey类型")

        # 验证公钥确实是由该私钥派生出来的
        self.assertEqual(private_key.get_verifying_key(), public_key, "公钥与私钥应匹配")

    def test_sign_and_verify_flow(self):
        """
        测试签名和验证的完整流程，包括成功和失败的场景。
        """
        # 准备数据和密钥对
        private_key, public_key = generate_keypair()
        message = b"this is a test message for signing"

        # 1. 签名
        signature = sign_data(message, private_key)
        self.assertIsInstance(signature, bytes, "签名应为bytes类型")

        # 2. 成功验证（使用正确的密钥和数据）
        is_valid = verify_signature(message, signature, public_key)
        self.assertTrue(is_valid, "使用正确的密钥和数据时，验证应成功")

        # 3. 失败验证（数据被篡改）
        tampered_message = b"this is a tampered message"
        is_valid_tampered = verify_signature(tampered_message, signature, public_key)
        self.assertFalse(is_valid_tampered, "数据被篡改时，验证应失败")

        # 4. 失败验证（使用了错误的公钥）
        other_private_key, other_public_key = generate_keypair()
        is_valid_wrong_key = verify_signature(message, signature, other_public_key)
        self.assertFalse(is_valid_wrong_key, "使用错误的公钥时，验证应失败")


# --- 使测试文件可以直接运行 ---
if __name__ == '__main__':
    unittest.main()