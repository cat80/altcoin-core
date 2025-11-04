import unittest
import time
import hashlib
import os
import secrets
import math

class BlockValidator:
    """
    一个包含区块验证相关静态方法的类
    """
    DIFFICULTY_1_BITS = 486604799 # 0x1d00ffff
    DIFFICULTY_1_TARGET = 0x00000000ffff0000000000000000000000000000000000000000000000000000

    @staticmethod
    def bits_to_target(bits: int) -> int:
        if isinstance(bits, str):
            bits = int(bits, 16)
        exponent = bits >> 24
        coefficient = bits & 0x00ffffff
        return coefficient << ((exponent - 3) * 8)

    @staticmethod
    def estimate_difficulty_from_bits(bits: int) -> float:
        current_target = BlockValidator.bits_to_target(bits)
        if current_target == 0: return float('inf')
        return BlockValidator.DIFFICULTY_1_TARGET / current_target

    @staticmethod
    def target_to_bits(target: int) -> int:
        """
        [新增] 根据目标值 Target 反推计算 bits
        """
        if target == 0:
            return 0

        # 获取 target 的二进制长度，计算 exponent
        # (target.bit_length() + 7) // 8 计算出存储该数字所需的字节数
        exponent = (target.bit_length() + 7) // 8

        # 计算 coefficient
        shift = (exponent - 3) * 8
        coefficient = target >> shift

        # 根据比特币协议，如果 coefficient 的最高位（第24位）是1，
        # 为了避免被当成负数，需要增加 exponent 并将 coefficient 右移8位
        if coefficient & 0x00800000:
            exponent += 1
            coefficient >>= 8

        # 组合成 bits
        return (exponent << 24) | coefficient


def format_time(seconds):
    """将秒数格式化为更易读的时间字符串"""
    if seconds < 0.01:
        return f"{seconds*1000:.2f} 毫秒"
    if seconds < 60:
        return f"{seconds:.2f} 秒"
    minutes, seconds = divmod(seconds, 60)
    hours, minutes = divmod(minutes, 60)
    days, hours = divmod(hours, 24)
    years, days = divmod(days, 365.25)

    parts = []
    if years > 0: parts.append(f"{int(years)}年")
    if days > 0: parts.append(f"{int(days)}天")
    if hours > 0: parts.append(f"{int(hours)}小时")
    if minutes > 0: parts.append(f"{int(minutes)}分钟")
    if seconds > 0: parts.append(f"{seconds:.2f}秒")
    return " ".join(parts) if parts else "0秒"


class TestMining(unittest.TestCase):

    # ... (之前的 test_bits_to_target 和 testValidation 方法保持不变) ...
    def test_bits_to_target(self):
        bits= 486604799
        move_left = ((bits>>24)-3)*8
        target = (bits&0x00ffffff)<<move_left
        print('bits:',bits,target)
        print('val calc:',BlockValidator.bits_to_target(bits))

    def testValidation(self):
        # first block bits
        test_dict = {
            'block_1':[486604799,'00000000839a8e6886ab5951d76f411475428afc90947ee320161bbf18eb6048'],
            'block_450000': [402836551, '0000000000000000014083723ed311a461c648068af8cef8a19dcd620c07a20b'],
            'block_900000': [386021236, '000000000000000000010538edbfd2d5b809a33dd83f284aeea41c6d0d96968a'],
        }
        print("\n--- [Running Test: Block Validation and Difficulty Estimation] ---")
        for block_num,block_header in test_dict.items():
            bits,block_hash = block_header
            target = BlockValidator.bits_to_target(bits)
            difficulty = BlockValidator.estimate_difficulty_from_bits(bits)

            print(f"\n======== {block_num} ========")
            print(f"Bits: {bits} (0x{bits:x})")
            print(f"Target: 0x{target.to_bytes(32, 'big').hex()}")
            print(f"Difficulty: {difficulty:,.2f}")

            block_hash_int = int.from_bytes(bytes.fromhex(block_hash),'big')
            self.assertLessEqual(block_hash_int, target)
            print(f"Hash Valid: {block_hash_int <= target}")
        print("="*40)

    def test_mining_simulation_and_estimation(self):
        """
        模拟挖矿过程，并估算在不同难度下的理论耗时
        """
        print("\n--- [Running Test: Mining Simulation and Time Estimation] ---")

        # 1. 测量本机算力
        print("\nStep 1: 正在测量本机单核算力...")
        hashes_to_test = 200_000
        header_data = secrets.token_bytes(76)

        start_time = time.time()
        for nonce in range(hashes_to_test):
            nonce_bytes = nonce.to_bytes(4, 'big')
            h = hashlib.sha256(header_data + nonce_bytes).digest()
            h2 = hashlib.sha256(h).digest()
        end_time = time.time()

        elapsed_time = end_time - start_time
        hashrate = hashes_to_test / elapsed_time
        print(f"本机单核算力: {hashrate:,.2f} H/s (次哈希/秒)")

        # ... (步骤2和3与之前相同，这里为了简洁可以省略或注释掉) ...
        print("\nStep 2 & 3: 估算真实难度下的理论挖矿耗时 (基于本机算力)...")
        # 此处省略之前的模拟和估算代码，聚焦于新的逆向计算
        # ...

    def test_time_to_difficulty_conversion(self):
        """
        [新增] 根据本机算力和期望时间，反推难度、Bits和Target
        """
        print("\n--- [Running Test: Time-to-Difficulty Conversion] ---")
        # 1. 再次测量算力以确保准确
        print("正在测量本机单核算力...")
        hashes_to_test = 200_000
        header_data = secrets.token_bytes(76)
        start_time = time.time()
        for nonce in range(hashes_to_test):
            nonce_bytes = nonce.to_bytes(4, 'big')
            h = hashlib.sha256(header_data + nonce_bytes).digest()
            h2 = hashlib.sha256(h).digest()
        end_time = time.time()
        hashrate = hashes_to_test / (end_time - start_time)
        print(f"本机单核算力: {hashrate:,.2f} H/s")

        # 2. 定义要计算的时间列表
        times_to_test = [1,3, 5, 10, 30,60, 600,3600,3600*24]

        for desired_seconds in times_to_test:
            print(f"\n======== 期望挖矿时间: {format_time(desired_seconds)} ========")

            # 期望的哈希次数 = 算力 * 时间
            expected_hashes = hashrate * desired_seconds

            # 难度 = 期望哈希次数 / 2^32
            difficulty = expected_hashes / (2**32)

            # 目标值 = 难度1目标值 / 难度
            # 防止除以一个极小的数导致溢出
            if difficulty == 0: continue
            target = int(BlockValidator.DIFFICULTY_1_TARGET / difficulty)

            # 目标值不能超过最大值 (即难度1的目标)
            # if target > BlockValidator.DIFFICULTY_1_TARGET:
            #     target = BlockValidator.DIFFICULTY_1_TARGET

            # 根据目标值反推bits
            bits = BlockValidator.target_to_bits(target)

            print(f"所需难度 (Difficulty): {difficulty:.6f}")
            print(f"计算出的 Bits: {bits} (0x{bits:x})")
            print(f"对应的 Target (目标哈希): 0x{target.to_bytes(32, 'big').hex()}")


# 运行测试
if __name__ == '__main__':
    unittest.main(verbosity=2)