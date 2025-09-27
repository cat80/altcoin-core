"""
AltCoin的密码学工具集。

该模块提供了核心的密码学功能，包括哈希、密钥对生成、签名和签名验证。
所有操作均基于ECDSA算法和SECP256k1曲线，这是加密货币领域的通用标准。
"""
import hashlib
import ecdsa
import  base58

# 定义全局使用的椭圆曲线，与比特币和以太坊保持一致。
CURVE = ecdsa.SECP256k1
# 定义地址版本号前缀 (0x00 类似于比特币主网地址)
ADDRESS_VERSION = b'\x00'

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
    except Exception as  ex:
        raise ex


def get_address_by_public_key(public_key: ecdsa.VerifyingKey, version: bytes = ADDRESS_VERSION) -> str:
    """
    根据公钥计算出带有校验和的Base58Check地址。
    流程: Base58Check( Version + HASH160(PublicKey) + Checksum )

    :param public_key: 公钥对象。
    :param version: 地址版本前缀，默认为0x00。
    :return: Base58Check编码的地址字符串。
    """
    # 1. HASH160 = RIPEMD160(SHA256(PublicKey))
    #    ecdsa库中的公钥to_string()默认返回未压缩格式(65字节)，我们需要用它
    sha256_hash = hashlib.sha256(public_key.to_string()).digest()
    ripemd160 = hashlib.new('ripemd160')
    ripemd160.update(sha256_hash)
    pubkey_hash = ripemd160.digest()  # 得到20字节的公钥哈希

    # 2. 添加版本前缀
    versioned_payload = version + pubkey_hash

    # 3. 计算校验和 (双重SHA256哈希的前4个字节)
    checksum = hash_data(versioned_payload)[:4]

    # 4. 拼接最终数据并进行Base58编码
    final_bytes = versioned_payload + checksum
    address = base58.b58encode(final_bytes).decode('utf-8')

    return address


def is_validate_address(address: str, version: bytes = ADDRESS_VERSION) -> bool:
    """
    校验一个Base58Check地址的格式和校验和是否正确。

    :param address: 需要校验的地址字符串。
    :param version: 期望的地址版本前缀。
    :return: 如果地址有效，返回True，否则返回False。
    """
    try:
        # 1. Base58解码
        decoded_bytes = base58.b58decode(address.encode('utf-8'))

        # 2. 检查长度是否正确 (1字节版本 + 20字节哈希 + 4字节校验和)
        if len(decoded_bytes) != 25:
            return False
        # 3. 检查版本号是否匹配
        if decoded_bytes[:1] != version:
            return False
        # 4. 分离数据和校验和
        payload = decoded_bytes[:-4]
        checksum_from_address = decoded_bytes[-4:]

        # 5. 重新计算校验和并进行比较
        calculated_checksum = hash_data(payload)[:4]

        return checksum_from_address == calculated_checksum

    except Exception:
        # 任何解码或格式错误都视为无效地址
        return False

def address_public_key_is_match( address,public_key)->bool:
    """
        某个地址是否属于这个publickey是否一致
    :param public_key:
    :param address:
    :return:
    """
    return get_address_by_public_key(public_key) == address