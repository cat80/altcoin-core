import unittest
import tempfile
import os
import shutil
from unittest.mock import patch, mock_open, MagicMock

from core.wallet import Wallet
from utils import crypto
import ecdsa


class TestWallet(unittest.TestCase):
    def setUp(self):
        """测试前的准备工作"""
        # 创建临时目录用于测试
        self.test_dir = tempfile.mkdtemp()
        
        # 生成一个测试钱包
        self.wallet = Wallet.generate()
        
        # 创建测试数据
        self.test_data = b"test data for signing"
        self.test_private_key_hex = "9f108f3d2d98f730d5f8e6be6e8c3bc39558f0b1a6b4447b333d9450b0c07463"
        
    def tearDown(self):
        """测试后的清理工作"""
        # 清理临时目录
        shutil.rmtree(self.test_dir, ignore_errors=True)
    
    def test_init_with_valid_private_key(self):
        """测试使用有效的私钥初始化钱包"""
        # 生成一个新的私钥
        private_key, _ = crypto.generate_keypair()
        
        # 使用私钥创建钱包
        wallet = Wallet(private_key)
        
        # 验证钱包属性
        self.assertIsInstance(wallet.private_key, ecdsa.SigningKey)
        self.assertIsInstance(wallet.public_key, ecdsa.VerifyingKey)
        self.assertIsInstance(wallet.address, str)
        self.assertTrue(len(wallet.address) > 0)
        
    def test_init_with_invalid_private_key(self):
        """测试使用无效的私钥初始化钱包"""
        # 尝试使用非ecdsa.SigningKey对象初始化钱包
        with self.assertRaises(TypeError) as context:
            Wallet("invalid_private_key")
            
        # 验证异常消息
        self.assertIn("private_key 必须是 ecdsa.SigningKey 类型", str(context.exception))
        
    def test_generate(self):
        """测试生成新钱包"""
        # 生成钱包
        wallet = Wallet.generate()
        
        # 验证钱包属性
        self.assertIsInstance(wallet, Wallet)
        self.assertIsInstance(wallet.private_key, ecdsa.SigningKey)
        self.assertIsInstance(wallet.public_key, ecdsa.VerifyingKey)
        self.assertIsInstance(wallet.address, str)
        self.assertTrue(len(wallet.address) > 0)

    def test_generator_wallets(self):
        wallet_key_path = f'/mnt/d/prj/web3/altcoin-core/nodes-data/wallet-key/'
        for i in range(10):
            wallet = Wallet.generate()
            print(wallet)
            wallet.save_to_file(f"{wallet_key_path}{wallet.get_address()}")

    def test_load_wallet(self):
        pass
        # wallet_key_path = f'/mnt/d/prj/web3/altcoin-core/nodes-data/wallet-key/main_key'
        # wallet = Wallet.from_file(wallet_key_path)
        # print(wallet.get_address())
    def test_from_hex_with_valid_hex(self):
        """测试从有效的十六进制字符串创建钱包"""
        # 从十六进制字符串创建钱包
        wallet = Wallet.from_hex(self.test_private_key_hex)
        
        # 验证钱包属性
        self.assertIsInstance(wallet, Wallet)
        self.assertIsInstance(wallet.private_key, ecdsa.SigningKey)
        self.assertIsInstance(wallet.public_key, ecdsa.VerifyingKey)
        self.assertIsInstance(wallet.address, str)
        self.assertTrue(len(wallet.address) > 0)
        
    def test_from_hex_with_invalid_hex(self):
        """测试从无效的十六进制字符串创建钱包"""
        # 使用无效的十六进制字符串
        invalid_hex = "invalid_hex_string"
        
        # 尝试从无效的十六进制字符串创建钱包
        with self.assertRaises(ValueError):
            Wallet.from_hex(invalid_hex)
            
    def test_from_hex_with_wrong_length(self):
        """测试从长度错误的十六进制字符串创建钱包"""
        # 使用长度错误的十六进制字符串
        wrong_length_hex = "9f108f3d2d98f730d5f8e6be6e8c3bc39558f0b1a6b4447b333d9450b0c074"  # 缺少一个字符
        
        # 尝试从长度错误的十六进制字符串创建钱包
        with self.assertRaises(Exception):  # 可能抛出多种异常
            Wallet.from_hex(wrong_length_hex)
            

        
    @patch('src.utils.crypto.load_key_from_pem')
    def test_from_file_not_found(self, mock_load_key_from_pem):
        """测试从不存在的文件加载钱包"""
        # 模拟FileNotFoundError异常
        mock_load_key_from_pem.side_effect = FileNotFoundError("File not found")
        
        # 尝试从不存在的文件创建钱包
        test_filepath = os.path.join(self.test_dir, "nonexistent_wallet.pem")

            
    def test_get_address(self):
        """测试获取钱包地址"""
        # 获取钱包地址
        address = self.wallet.get_address()
        
        # 验证地址
        self.assertIsInstance(address, str)
        self.assertEqual(address, self.wallet.address)
        self.assertTrue(len(address) > 0)

    def test_save_to_file(self):
        """测试保存钱包到文件"""
        # 保存钱包到文件
        test_filepath = os.path.join(self.test_dir, "saved_wallet.pem")
        self.wallet.save_to_file(test_filepath)

        new_wallet = Wallet.from_file(test_filepath)
        self.assertEqual(self.wallet.get_address(),new_wallet.get_address())



    def test_sign(self):
        """测试数据签名"""
        # 对数据进行签名
        signature = self.wallet.sign(self.test_data)
        
        # 验证签名
        self.assertIsInstance(signature, bytes)
        self.assertTrue(len(signature) > 0)
        
        # 验证签名有效性
        # 使用公钥验证签名
        public_key = self.wallet.public_key
        self.assertTrue(crypto.verify_signature(self.test_data, signature, public_key))
        
    def test_sign_empty_data(self):
        """测试对空数据进行签名"""
        # 对空数据进行签名
        empty_data = b""
        signature = self.wallet.sign(empty_data)
        
        # 验证签名
        self.assertIsInstance(signature, bytes)
        self.assertTrue(len(signature) > 0)
        
        # 验证签名有效性
        public_key = self.wallet.public_key
        self.assertTrue(crypto.verify_signature(empty_data, signature, public_key))
        
    def test_repr(self):
        """测试钱包对象的字符串表示"""
        # 获取钱包的字符串表示
        repr_str = repr(self.wallet)
        
        # 验证字符串表示
        self.assertIsInstance(repr_str, str)
        self.assertIn("<Wallet address=", repr_str)
        self.assertIn(self.wallet.address, repr_str)
        
    def test_address_derivation_consistency(self):
        """测试地址推导的一致性"""
        # 从相同的私钥创建两个钱包
        private_key, _ = crypto.generate_keypair()
        wallet1 = Wallet(private_key)
        wallet2 = Wallet(private_key)
        
        # 验证两个钱包的地址相同
        self.assertEqual(wallet1.get_address(), wallet2.get_address())
        
    def test_different_wallets_have_different_addresses(self):
        """测试不同钱包具有不同的地址"""
        # 创建两个不同的钱包
        wallet1 = Wallet.generate()
        wallet2 = Wallet.generate()
        
        # 验证两个钱包的地址不同
        self.assertNotEqual(wallet1.get_address(), wallet2.get_address())
        
    def test_signature_verification_with_different_data(self):
        """测试使用不同数据验证签名"""
        # 对数据进行签名
        signature = self.wallet.sign(self.test_data)
        
        # 使用不同的数据验证签名应该失败
        different_data = b"different data"
        public_key = self.wallet.public_key
        self.assertFalse(crypto.verify_signature(different_data, signature, public_key))


if __name__ == '__main__':
    unittest.main()