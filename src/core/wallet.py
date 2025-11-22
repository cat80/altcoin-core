"""
钱包模块，提供了一个高级接口来管理用户的密钥、地址和签名操作。
"""

import ecdsa
from utils import crypto

class Wallet:
    """
    Wallet类封装了与用户密钥对和地址相关的所有操作。

    它内部管理一个私钥及其对应的公钥和地址，并提供创建、加载、
    保存和使用钱包的便捷方法。
    """

    def __init__(self, private_key: ecdsa.SigningKey):
        """
        初始化一个钱包实例。

        这个构造函数通常不直接调用，推荐使用类方法 `generate()` 或 `from_file()` 来创建实例。

        :param private_key: ecdsa.SigningKey 类型的私钥对象。
        """
        if not isinstance(private_key, ecdsa.SigningKey):
            raise TypeError("private_key 必须是 ecdsa.SigningKey 类型")

        # 保存私钥对象
        self.private_key = private_key
        # 从私钥派生出公钥对象
        self.public_key = private_key.get_verifying_key()
        # 根据公钥计算出钱包地址
        self.address = crypto.get_address_by_public_key(self.public_key)

    @staticmethod
    def generate():
        """
        静态方法：生成一个新的钱包。

        这会创建一个全新的私钥，并用它来实例化一个新的Wallet对象。
        这是创建新钱包推荐的方式。

        :return: 一个新的 Wallet 实例。
        """
        private_key, _ = crypto.generate_keypair()
        return Wallet(private_key)

    @staticmethod
    def from_file(filepath: str):
        """
        静态方法：从一个PEM格式的文件中加载钱包。

        :param filepath: 私钥文件（.pem）的路径。
        :return: 一个从文件加载的 Wallet 实例。
        :raises FileNotFoundError: 如果指定路径的文件不存在。
        """
        private_key, _ = crypto.load_key_from_pem(filepath)
        return Wallet(private_key)
    
    @staticmethod
    def from_hex(private_key_hex: str):
        """
        静态方法：从十六进制字符串表示的私钥创建钱包。

        :param private_key_hex: 64个字符的十六进制私钥字符串。
        :return: 一个新的 Wallet 实例。
        """
        private_key_bytes = bytes.fromhex(private_key_hex)
        private_key = ecdsa.SigningKey.from_string(private_key_bytes, curve=crypto.CURVE)
        return Wallet(private_key)

    def get_address(self) -> str:
        """
        获取钱包的Base58Check编码地址。

        :return: 钱包地址字符串。
        """
        return self.address

    def save_to_file(self, filepath: str):
        """
        将当前钱包的私钥以PEM格式保存到文件。

        如果目录不存在，会自动创建。

        :param filepath: 希望保存私钥的文件路径。
        """
        crypto.save_to_pem(self.private_key, filepath)

    def sign(self, data: bytes) -> bytes:
        """
        使用钱包的私钥对给定的数据进行签名。

        注意：函数内部会自动对数据进行双重SHA256哈希，然后再签名。

        :param data: 需要被签名的原始数据（bytes类型）。
        :return: 交易的签名（bytes类型）。
        """
        return crypto.sign_data(data, self.private_key)

    def __repr__(self):
        """
        返回钱包对象的字符串表示形式，方便调试。
        """
        return f"<Wallet address={self.address}>"
