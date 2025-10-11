"""
AltCoin的通用工具集方法，该方法很多依赖默认的配置。

该模块提供了核心的密码学功能，包括哈希、密钥对生成、签名和签名验证。
所有操作均基于ECDSA算法和SECP256k1曲线，这是加密货币领域的通用标准。
"""

from config import *


def get_block_reward(height: int) -> int:
    """
        根据区块高度计算区块奖励。
    """
    halvings = height // REWARD_CUTOFF_BLOCKS
    reward = INITIAL_BLOCK_REWARD >> halvings
    return reward if reward > 0 else 0


def bits_to_target(bits: int) -> int:
    """
    :return:
    :param bits:
    :return: 将区块头中的bits字段转换为一个大的整数目标值。
            cat80 add:
                这里有一个核心的难度存储问题：bits是四个字节的整数，在block_header里面是小端存储的。成功序列化为整数后。
                bits的大端如：0x1d00ffff,第一个字节代表左移的量这里是,后三个字节组成的大端整数，则代表基础的难难度。exponent-3个字节的原因是位置的原始数据已经包含了三个字节。可以简单的计算如果bits为0x200ffff,则意味着每16次就能挖到矿一次。难度调节也是根据前N个区块的时间差，与预期的时间比较，动态的上调或者下调难度
    """
    exponent = bits >> 24
    mantissa = bits & 0x00ffffff
    move_left = (exponent-3)*8
    target = mantissa << move_left
    return target

def target_to_bits(target: int) -> int:
    """
    将一个大的整数目标值 target 转换为紧凑的 bits 格式。
    这是 bits_to_target 的反向函数。
    """
    if target == 0:
        return 0

    # 1. 计算target需要多少个字节来表示。
    #    int.bit_length() 返回表示该整数所需的最小位数。
    #    (target.bit_length() + 7) // 8 是计算字节数的标准方法。
    size_in_bytes = (target.bit_length() + 7) // 8
    exponent = size_in_bytes

    # 2. 计算mantissa。我们需要target的最高有效3个字节。
    #    为此，我们将target右移 (size_in_bytes - 3) * 8 位。
    if size_in_bytes <= 3:
        # 如果target本身小于等于3字节, mantissa就是target左移以填满3字节
        shift = (3 - size_in_bytes) * 8
        mantissa = target << shift
    else:
        # 如果target大于3字节，我们通过右移来截断，只保留最重要的部分
        shift = (size_in_bytes - 3) * 8
        mantissa = target >> shift

    # 3. 标准化处理 (比特币核心规则):
    #    如果mantissa的最高有效位(第24位)是1，即 mantissa >= 0x800000，
    #    则需要将mantissa再右移8位(一个字节)，并相应地将exponent加1。
    #    这确保了mantissa的最高位永远是0，避免被解释为负数。
    if mantissa & 0x00800000:
        mantissa >>= 8
        exponent += 1

    # 4. 组合exponent和mantissa
    #    将exponent左移24位，然后用或操作(|)与mantissa合并。
    bits = (exponent << 24) | mantissa
    return bits