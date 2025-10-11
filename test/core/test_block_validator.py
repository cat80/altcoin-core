import unittest
from unittest.mock import Mock, patch
import io

from core.block_validator import BlockValidator
from core.block import Block
from core.block_header import BlockHeader
from core.transaction import Transaction, TxIn, TxOut
from core.chain_state import ChainState
from core.block_index import BlockIndex
from storage.rocksdb_wrapper import RocksDBWrapper


class TestBlockValidator(unittest.TestCase):

    def setUp(self):
        """测试前的准备工作"""
        # 创建测试交易
        txin1 = TxIn(
            prev_tx_hash=b'\x00' * 32,
            prev_tx_out_index=0,
            unlocking_script=b'test_unlock_script_1'
        )
        txout1 = TxOut(
            value=1000,
            locking_script=b'test_lock_script_1'
        )
        self.test_transaction = Transaction(
            version=1,
            tx_ins=[txin1],
            tx_outs=[txout1],
            lock_time=0
        )

        # 创建coinbase交易
        coinbase_txin = TxIn.create_coinbase_txin(b'Coinbase Data - AltCoin Mined!')
        coinbase_txout = TxOut(
            value=5000,
            locking_script=b'\x00' * 20
        )
        self.coinbase_transaction = Transaction(
            version=1,
            tx_ins=[coinbase_txin],
            tx_outs=[coinbase_txout],
            lock_time=0
        )

        # 创建测试区块头
        self.test_header = BlockHeader(
            version=1,
            prev_block_hash=b'\x00' * 32,
            merkle_root=b'\x00' * 32,
            timestamp=1234567890,
            bits=0x1d00ffff,
            nonce=12345
        )

        # 创建测试区块
        self.test_block = Block(
            header=self.test_header,
            transactions=[self.coinbase_transaction, self.test_transaction]
        )

    def test_bits_to_target(self):
        """测试bits到target的转换"""
        # 测试一个典型的bits值
        bits = 0x1d00ffff
        target = BlockValidator.bits_to_target(bits)
        expected_target = 0x00ffff << (0x1d - 3) * 8
        self.assertEqual(target, expected_target)

        # 测试另一个bits值
        bits = 0x1f00ffff
        target = BlockValidator.bits_to_target(bits)
        expected_target = 0x00ffff << (0x1f - 3) * 8
        self.assertEqual(target, expected_target)

    def test_get_block_reward(self):
        """测试区块奖励计算"""
        # 创世区块奖励
        from config import INITIAL_BLOCK_REWARD, REWARD_CUTOFF_BLOCKS
        reward = BlockValidator.get_block_reward(0)
        self.assertEqual(reward, INITIAL_BLOCK_REWARD)

        # 第一个减半前的区块
        reward = BlockValidator.get_block_reward(REWARD_CUTOFF_BLOCKS - 1)
        self.assertEqual(reward, INITIAL_BLOCK_REWARD)

        # 第一次减半后的区块
        reward = BlockValidator.get_block_reward(REWARD_CUTOFF_BLOCKS)
        self.assertEqual(reward, INITIAL_BLOCK_REWARD // 2)

        # 第二次减半后的区块
        reward = BlockValidator.get_block_reward(REWARD_CUTOFF_BLOCKS * 2)
        self.assertEqual(reward, INITIAL_BLOCK_REWARD // 4)

        # 测试奖励最终变为0的情况
        reward = BlockValidator.get_block_reward(REWARD_CUTOFF_BLOCKS * 20)
        self.assertEqual(reward, INITIAL_BLOCK_REWARD // (2**20))

        # 测试奖励为0的情况
        reward = BlockValidator.get_block_reward(REWARD_CUTOFF_BLOCKS * 50)
        self.assertEqual(reward, 0)

    def test_check_block_header(self):
        """测试区块头验证"""
        # 创建一个有效的区块头（哈希值小于目标值）
        header = BlockHeader(
            version=1,
            prev_block_hash=b'\x00' * 32,
            merkle_root=b'\x00' * 32,
            timestamp=1234567890,
            bits=0x1f00ffff,  # 相对较低的难度
            nonce=12345
        )

        # 使用patch确保哈希值小于目标值
        with patch.object(BlockHeader, 'hash', return_value=b'\x00' * 32):
            result = BlockValidator.check_block_header(header)
            self.assertTrue(result)

        # 创建一个无效的区块头（哈希值大于目标值）
        header2 = BlockHeader(
            version=1,
            prev_block_hash=b'\x00' * 32,
            merkle_root=b'\x00' * 32,
            timestamp=1234567890,
            bits=0x0400ffff,  # 非常高的难度
            nonce=12345
        )

        # 使用patch确保哈希值大于目标值
        with patch.object(BlockHeader, 'hash', return_value=b'\xff' * 32):
            result = BlockValidator.check_block_header(header2)
            self.assertFalse(result)

    def test_check_merkle_root(self):
        """测试默克尔根验证"""
        # 创建一个区块，其默克尔根与交易不匹配
        header = BlockHeader(
            version=1,
            prev_block_hash=b'\x00' * 32,
            merkle_root=b'\x00' * 32,  # 错误的默克尔根
            timestamp=1234567890,
            bits=0x1d00ffff,
            nonce=12345
        )

        block = Block(
            header=header,
            transactions=[self.coinbase_transaction, self.test_transaction]
        )

        # 验证应该失败，因为默克尔根不匹配
        result = BlockValidator.check_merkle_root(block)
        self.assertFalse(result)

    def test_check_block_transactions_no_transactions(self):
        """测试区块交易验证 - 没有交易的情况"""
        # 创建一个没有交易的区块
        block = Block(header=self.test_header, transactions=[])

        # 创建mock chain_state
        chain_state = Mock(spec=ChainState)

        result = BlockValidator.check_block_transactions(block, chain_state, 1)
        self.assertFalse(result)

    def test_check_block_transactions_no_coinbase(self):
        """测试区块交易验证 - 没有coinbase交易"""
        block = Block(
            header=self.test_header,
            transactions=[self.test_transaction]  # 没有coinbase交易
        )

        chain_state = Mock(spec=ChainState)

        result = BlockValidator.check_block_transactions(block, chain_state, 1)
        self.assertFalse(result)

    def test_check_block_transactions_multiple_coinbase(self):
        """测试区块交易验证 - 多个coinbase交易"""
        block = Block(
            header=self.test_header,
            transactions=[self.coinbase_transaction, self.coinbase_transaction]  # 两个coinbase交易
        )

        chain_state = Mock(spec=ChainState)

        result = BlockValidator.check_block_transactions(block, chain_state, 1)
        self.assertFalse(result)

    def test_check_block_transactions_coinbase_reward_too_high(self):
        """测试区块交易验证 - coinbase奖励过高"""
        # 创建一个奖励过高的coinbase交易
        coinbase_txin = TxIn.create_coinbase_txin(b'Coinbase Data - AltCoin Mined!')
        coinbase_txout = TxOut(
            value=1000000000000,  # 过高的奖励
            locking_script=b'\x00' * 20
        )
        high_reward_coinbase = Transaction(
            version=1,
            tx_ins=[coinbase_txin],
            tx_outs=[coinbase_txout],
            lock_time=0
        )

        block = Block(
            header=self.test_header,
            transactions=[high_reward_coinbase, self.test_transaction]
        )

        chain_state = Mock(spec=ChainState)

        result = BlockValidator.check_block_transactions(block, chain_state, 1)
        self.assertFalse(result)

    def test_check_block(self):
        """测试完整区块验证"""
        # 创建mock对象
        chain_state = Mock(spec=ChainState)
        block_index = Mock(spec=BlockIndex)
        prev_header_info = {'height': 10}

        # 模拟验证失败的情况
        with patch.object(BlockValidator, 'check_merkle_root', return_value=False):
            result = BlockValidator.check_block(self.test_block, chain_state, block_index, prev_header_info)
            self.assertFalse(result)

        # 模拟验证成功的情况
        with patch.object(BlockValidator, 'check_merkle_root', return_value=True):
            with patch.object(BlockValidator, 'check_block_transactions', return_value=True):
                result = BlockValidator.check_block(self.test_block, chain_state, block_index, prev_header_info)
                self.assertTrue(result)


if __name__ == '__main__':
    unittest.main()