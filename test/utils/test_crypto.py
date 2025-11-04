import unittest
import ecdsa
from utils.crypto import *

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
        print(f'sign len:{len(signature)}')
        print(f'public_key len:{public_key.curve.baselen}')
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

    def test_address_generation_and_validation(self):
        """
        测试地址生成和校验的完整流程。
        使用一个固定的私钥，以确保每次测试生成的地址都是相同的。
        """
        # 这是一个固定的、用于测试的私钥（32字节）
        test_private_key_bytes = bytes.fromhex(
            '18e14a7b6a307f426a94f8114701e7c8e774e7f9a47e2c2035db29a206321725'
        )

        # 从该私钥生成密钥对
        private_key = ecdsa.SigningKey.from_string(test_private_key_bytes, curve=CURVE)
        public_key = private_key.get_verifying_key()

        # 预期的、由上面这个私钥生成的正确地址
        expected_address = "1LRdmypMdxPWKMo3PQmMdbupCabYvMyvP1"

        # 1. 测试地址生成
        generated_address = get_address_by_public_key(public_key)
        self.assertEqual(generated_address, expected_address, "生成的地址与预期不符")

        # 2. 测试有效地址的校验
        self.assertTrue(is_validate_address(expected_address), "正确的地址应该通过校验")

    def test_invalid_addresses(self):
        """
        测试几种典型的无效地址场景。
        """
        # 场景一：校验和错误 (将最后一个字符M改成N)
        address_bad_checksum = "16UwLL9Risc3QfPqBUvKofHmBQ7wMtjvN"
        self.assertFalse(is_validate_address(address_bad_checksum), "校验和错误的地址应验证失败")

        # 场景二：包含非法字符 (将'v'替换成'l'，'l'不在Base58字符集中)
        address_invalid_char = "16UwLL9Risc3QfPqBUvKofHmBQ7wMtjlM"
        self.assertFalse(is_validate_address(address_invalid_char), "包含非法字符的地址应验证失败")

        # 场景三：长度错误
        address_too_short = "16UwLL9Risc3QfPqBUvKofHmBQ7w"
        self.assertFalse(is_validate_address(address_too_short), "长度过短的地址应验证失败")

        # 场景四：版本号错误
        # 我们用一个虚构的测试网版本号(0x6f)来生成一个地址
        testnet_version = b'\x6f'
        private_key, public_key = generate_keypair()
        testnet_address = get_address_by_public_key(public_key, version=testnet_version)
        # 使用默认的主网版本号(0x00)来校验这个测试网地址，应该会失败
        self.assertFalse(is_validate_address(testnet_address), "版本号不匹配的地址应验证失败")
        # 使用正确的测试网版本号来校验，应该会成功
        self.assertTrue(is_validate_address(testnet_address, version=testnet_version), "使用正确的版本号校验应成功")
    def test_address_from_public_key(self):
        """
            测试某一key是否来源说一个public key
        :return:
        """
        for i in range(0,5):
            prvate_key,public_key = generate_keypair()
            address = get_address_by_public_key(public_key)

            self.assertTrue(address_public_key_is_match(address,public_key))
            self.assertFalse(address_public_key_is_match(address+'a', public_key))

    def test_os(self):
        import sys
        import platform
        print('python version is:',sys.version)
        print('platform version is:',platform.system())

    def test_paris_use(self):

        pem_file = '/mnt/d/prj/web3/altcoin-core/test/tmp/test.pem'
        sk1 ,pk1 = generate_keypair()
        save_to_pem(sk1,pem_file)

        sk2,pk2 = load_key_from_pem(pem_file)

        print(sk1,sk2)
        print(pk1, pk2)
    def test_get_pars_and_address(self):
        privek,pubk=generate_keypair()
        addr = get_address_by_public_key(pubk)
        print(addr)
        print(f'bytes:[pk:{privek.to_string()},pubk:{privek.to_string()},addr:{privek.to_string()}],hdex:[pk:{privek.to_string().hex()},pubk:{pubk.to_string().hex()},addr:{addr.encode()}]')

    def test_combineation(self):
        """
            综合性做一些测试
        :return:
        """
        prk1, pubk1 = generate_keypair()
        sign_orgin = b'ad6161ew'
        sign_content = sign_data(sign_orgin, prk1)

        self.assertTrue(  verify_signature( sign_orgin,sign_content,pubk1))
# --- 使测试文件可以直接运行 ---
if __name__ == '__main__':
    unittest.main()