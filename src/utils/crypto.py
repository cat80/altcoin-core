"""
AltCoin的密码学工具集。

该模块提供了核心的密码学功能，包括哈希、密钥对生成、签名和签名验证。
所有操作均基于ECDSA算法和SECP256k1曲线，这是加密货币领域的通用标准。
"""
import hashlib
import ecdsa

# 定义全局使用的椭圆曲线，与比特币和以太坊保持一致。
CURVE = ecdsa.SECP256k1

def hash_data(data: bytes) -> bytes:
    """
    使用AltCoin的哈希算法（双重SHA256）对数据进行哈希。

    :param data: 需要哈希的字节数据。
    :return: 32字节的哈希结果（bytes类型）。
    """
    # 参考了bitcoin二次hash256的计算，从空间存储考虑可以像eth那样考虑使用20位的截取
    return hashlib.sha256(hashlib.sha256(data).digest()).digest()

def generate_keypair() -> (ecdsa.SigningKey, ecdsa.VerifyingKey):
    """
    生成一个新的ECDSA密钥对，用于交易签名。

    :return: 一个元组，包含 (私钥对象, 公钥对象)。
    """
    private_key = ecdsa.SigningKey.generate(curve=CURVE)
    public_key = private_key.get_verifying_key()
    return private_key, public_key

def sign_data(data: bytes, private_key: ecdsa.SigningKey) -> bytes:
    """
    使用私钥对数据进行签名。

    注意：标准实践是对数据的哈希进行签名，而不是原始数据。
    本函数已在内部处理了哈希计算。

    :param data: 需要签名的原始数据（bytes类型）。
    :param private_key: 用于签名的ecdsa.SigningKey私钥对象。
    :return: 签名的字节表示（bytes类型）。
    """
    data_hash = hash_data(data)
    return private_key.sign(data_hash)

def verify_signature(data: bytes, signature: bytes, public_key: ecdsa.VerifyingKey) -> bool:
    """
    根据数据和公钥，验证一个签名的有效性。

    :param data: 被签名的原始数据（bytes类型）。
    :param signature: 需要验证的签名（bytes类型）。
    :param public_key: 用于验证的ecdsa.VerifyingKey公钥对象。
    :return: 如果签名有效，返回True，否则返回False。
    """
    try:
        data_hash = hash_data(data)
        # 验证函数在失败时会抛出ecdsa.BadSignatureError异常。
        # 我们捕捉该异常并返回一个清晰的布尔值。
        return public_key.verify(signature, data_hash)
    except ecdsa.BadSignatureError:
        return False