import unittest
from unittest.mock import Mock, patch
import tempfile
import os
import sys
import io
from unittest.mock import MagicMock

# 添加项目根目录到sys.path，确保可以导入src目录下的模块
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from core.block_index import BlockIndex
from core.block_header import BlockHeader
from storage.sql_alchemy_wrapper import SQLAlchemyWrapper
from config import INITIAL_BITS, ADJUSTMENT_INTERVAL, TARGET_TIMESPAN, BLOCK_STATUS_VALID, BLOCK_STATUS_INVALID


class TestBlockIndex(unittest.TestCase):

    def setUp(self):
        """测试前的准备工作"""
        # 创建临时目录用于测试数据库
        self.test_dir = tempfile.mkdtemp()
        self.db_path = os.path.join(self.test_dir, 'test_index.db')
        
        # 创建SQLAlchemyWrapper实例
        self.sqldb = SQLAlchemyWrapper(self.db_path)
        self.sqldb.create_all_tables()
        
        # 创建BlockIndex实例
        self.block_index = BlockIndex(self.sqldb)
        
        # 创建测试用的区块头
        self.genesis_header = BlockHeader(
            version=1,
            prev_block_hash=b'\x00'*32,
            merkle_root=b'\x01'*32,
            timestamp=1234567890,
            bits=INITIAL_BITS,
            nonce=1000
        )
        
        self.block_header_1 = BlockHeader(
            version=1,
            prev_block_hash=self.genesis_header.hash(),
            merkle_root=b'\x02'*32,
            timestamp=1234567891,
            bits=INITIAL_BITS,
            nonce=1001
        )
        
        self.block_header_2 = BlockHeader(
            version=1,
            prev_block_hash=self.block_header_1.hash(),
            merkle_root=b'\x03'*32,
            timestamp=1234567892,
            bits=INITIAL_BITS,
            nonce=1002
        )

    def tearDown(self):
        # 清理临时目录
        import shutil
        shutil.rmtree(self.test_dir)

    def test_add_header_and_get_header_info(self):
        """测试添加区块头和获取区块头信息"""
        # 添加创世区块
        genesis_hash = self.genesis_header.hash()
        self.block_index.add_header(self.genesis_header, 0, 100.0, 0, 0, BLOCK_STATUS_VALID)
        
        # 获取创世区块信息
        genesis_info = self.block_index.get_header_info(genesis_hash)
        self.assertIsNotNone(genesis_info)
        self.assertEqual(genesis_info['block_hash'], genesis_hash)
        self.assertEqual(genesis_info['height'], 0)
        self.assertEqual(genesis_info['total_work'], 100.0)
        self.assertEqual(genesis_info['prev_block_hash'], b'\x00'*32)

    def test_get_genesis_block(self):
        """测试获取创世区块"""
        # 添加创世区块
        self.block_index.add_header(self.genesis_header, 0, 100.0, 0, 0, BLOCK_STATUS_VALID)
        
        # 获取创世区块
        genesis_info = self.block_index.get_genesis_block()
        self.assertIsNotNone(genesis_info)
        self.assertEqual(genesis_info['height'], 0)

    def test_get_tip(self):
        """测试获取主链顶端"""
        # 添加创世区块
        self.block_index.add_header(self.genesis_header, 0, 100.0, 0, 0, BLOCK_STATUS_VALID)
        
        # 添加第一个区块，工作量更大
        self.block_index.add_header(self.block_header_1, 1, 200.0, 0, 80, BLOCK_STATUS_VALID)
        
        # 获取顶端区块，应该是第一个区块
        tip = self.block_index.get_tip()
        self.assertIsNotNone(tip)
        self.assertEqual(tip['block_hash'], self.block_header_1.hash())
        self.assertEqual(tip['total_work'], 200.0)

    def test_get_ancestor(self):
        """测试获取祖先区块"""
        # 添加区块到索引
        self.block_index.add_header(self.genesis_header, 0, 100.0, 0, 0, BLOCK_STATUS_VALID)
        self.block_index.add_header(self.block_header_1, 1, 200.0, 0, 80, BLOCK_STATUS_VALID)
        self.block_index.add_header(self.block_header_2, 2, 300.0, 0, 160, BLOCK_STATUS_VALID)
        
        # 获取区块2的祖先（高度1）
        ancestor = self.block_index.get_ancestor(self.block_header_2.hash(), 1)
        self.assertIsNotNone(ancestor)
        self.assertEqual(ancestor['block_hash'], self.block_header_1.hash())
        self.assertEqual(ancestor['height'], 1)

    def test_find_common_ancestor_no_fork(self):
        """测试在没有分叉的情况下查找共同祖先"""
        # 添加区块到索引
        self.block_index.add_header(self.genesis_header, 0, 100.0, 0, 0, BLOCK_STATUS_VALID)
        self.block_index.add_header(self.block_header_1, 1, 200.0, 0, 80, BLOCK_STATUS_VALID)
        self.block_index.add_header(self.block_header_2, 2, 300.0, 0, 160, BLOCK_STATUS_VALID)
        
        # 查找共同祖先（同一链上的两个区块）
        common_ancestor, old_chain, new_chain = self.block_index.find_common_ancestor(
            self.block_header_1.hash(),  # 旧链tip
            self.block_header_2.hash()   # 新链tip
        )
        
        # 验证结果
        self.assertEqual(common_ancestor, self.block_header_1.hash())
        self.assertEqual(len(old_chain), 0)  # 旧链没有需要回滚的区块
        self.assertEqual(len(new_chain), 1)  # 新链有1个需要应用的区块
        self.assertEqual(new_chain[0]['block_hash'], self.block_header_2.hash())

    def test_find_common_ancestor_with_fork(self):
        """测试在有分叉的情况下查找共同祖先"""
        # 添加主链区块到索引
        self.block_index.add_header(self.genesis_header, 0, 100.0, 0, 0, BLOCK_STATUS_VALID)
        self.block_index.add_header(self.block_header_1, 1, 200.0, 0, 80, BLOCK_STATUS_VALID)
        self.block_index.add_header(self.block_header_2, 2, 300.0, 0, 160, BLOCK_STATUS_VALID)
        
        # 创建分叉链区块
        fork_block_header = BlockHeader(
            version=1,
            prev_block_hash=self.block_header_1.hash(),  # 从区块1分叉
            merkle_root=b'\x04'*32,
            timestamp=1234567893,
            bits=INITIAL_BITS,
            nonce=1003
        )
        self.block_index.add_header(fork_block_header, 2, 250.0, 0, 240, BLOCK_STATUS_VALID)
        
        # 查找共同祖先
        common_ancestor, old_chain, new_chain = self.block_index.find_common_ancestor(
            self.block_header_2.hash(),    # 旧链tip（主链）
            fork_block_header.hash()       # 新链tip（分叉链）
        )
        
        # 验证结果
        self.assertEqual(common_ancestor, self.block_header_1.hash())  # 共同祖先是区块1
        self.assertEqual(len(old_chain), 1)  # 旧链需要回滚1个区块（区块2）
        self.assertEqual(len(new_chain), 1)  # 新链需要应用1个区块（分叉区块）
        self.assertEqual(old_chain[0]['block_hash'], self.block_header_2.hash())
        self.assertEqual(new_chain[0]['block_hash'], fork_block_header.hash())

    def test_update_block_status(self):
        """测试更新单个区块状态"""
        # 添加区块
        self.block_index.add_header(self.genesis_header, 0, 100.0, 0, 0, BLOCK_STATUS_VALID)
        
        # 获取初始状态
        genesis_hash = self.genesis_header.hash()
        genesis_info = self.block_index.get_header_info(genesis_hash)
        self.assertEqual(genesis_info['status'], BLOCK_STATUS_VALID)
        
        # 更新状态为无效
        self.block_index.update_block_status(genesis_hash, BLOCK_STATUS_INVALID)
        
        # 验证状态已更新
        genesis_info = self.block_index.get_header_info(genesis_hash)
        self.assertEqual(genesis_info['status'], BLOCK_STATUS_INVALID)

    def test_update_blocks_status(self):
        """测试批量更新区块状态"""
        # 添加多个区块
        self.block_index.add_header(self.genesis_header, 0, 100.0, 0, 0, BLOCK_STATUS_VALID)
        self.block_index.add_header(self.block_header_1, 1, 200.0, 0, 80, BLOCK_STATUS_VALID)
        self.block_index.add_header(self.block_header_2, 2, 300.0, 0, 160, BLOCK_STATUS_VALID)
        
        # 获取初始状态
        genesis_hash = self.genesis_header.hash()
        block1_hash = self.block_header_1.hash()
        block2_hash = self.block_header_2.hash()
        
        genesis_info = self.block_index.get_header_info(genesis_hash)
        block1_info = self.block_index.get_header_info(block1_hash)
        block2_info = self.block_index.get_header_info(block2_hash)
        
        self.assertEqual(genesis_info['status'], BLOCK_STATUS_VALID)
        self.assertEqual(block1_info['status'], BLOCK_STATUS_VALID)
        self.assertEqual(block2_info['status'], BLOCK_STATUS_VALID)
        
        # 批量更新状态为无效
        self.block_index.update_blocks_status([genesis_hash, block1_hash], BLOCK_STATUS_INVALID)
        
        # 验证状态已更新
        genesis_info = self.block_index.get_header_info(genesis_hash)
        block1_info = self.block_index.get_header_info(block1_hash)
        block2_info = self.block_index.get_header_info(block2_hash)
        
        self.assertEqual(genesis_info['status'], BLOCK_STATUS_INVALID)
        self.assertEqual(block1_info['status'], BLOCK_STATUS_INVALID)
        self.assertEqual(block2_info['status'], BLOCK_STATUS_VALID)  # 这个区块状态应该未改变

    def test_get_header_by_height(self):
        """测试根据高度获取区块"""
        # 添加区块
        self.block_index.add_header(self.genesis_header, 0, 100.0, 0, 0, BLOCK_STATUS_VALID)
        self.block_index.add_header(self.block_header_1, 1, 200.0, 0, 80, BLOCK_STATUS_VALID)
        self.block_index.add_header(self.block_header_2, 2, 300.0, 0, 160, BLOCK_STATUS_VALID)
        
        # 根据高度获取区块
        genesis_info = self.block_index.get_header_by_height(0)
        block1_info = self.block_index.get_header_by_height(1)
        block2_info = self.block_index.get_header_by_height(2)
        non_existent_info = self.block_index.get_header_by_height(3)
        
        # 验证结果
        self.assertIsNotNone(genesis_info)
        self.assertEqual(genesis_info['height'], 0)
        self.assertEqual(genesis_info['block_hash'], self.genesis_header.hash())
        
        self.assertIsNotNone(block1_info)
        self.assertEqual(block1_info['height'], 1)
        self.assertEqual(block1_info['block_hash'], self.block_header_1.hash())
        
        self.assertIsNotNone(block2_info)
        self.assertEqual(block2_info['height'], 2)
        self.assertEqual(block2_info['block_hash'], self.block_header_2.hash())
        
        self.assertIsNone(non_existent_info)

    def test_calculate_required_bits_before_first_adjustment(self):
        """测试在第一个难度调整点之前的区块难度计算"""
        # 添加一些区块（少于ADJUSTMENT_INTERVAL个）
        self.block_index.add_header(self.genesis_header, 0, 100.0, 0, 0, BLOCK_STATUS_VALID)
        self.block_index.add_header(self.block_header_1, 1, 200.0, 0, 80, BLOCK_STATUS_VALID)
        self.block_index.add_header(self.block_header_2, 2, 300.0, 0, 160, BLOCK_STATUS_VALID)
        
        # 计算高度为5的区块的难度（小于ADJUSTMENT_INTERVAL）
        bits = self.block_index.calculate_required_bits(5)
        
        # 应该返回INITIAL_BITS
        self.assertEqual(bits, INITIAL_BITS)

    def test_calculate_required_bits_at_non_adjustment_point(self):
        """测试在非难度调整点的区块难度计算"""
        # 添加一些区块
        self.block_index.add_header(self.genesis_header, 0, 100.0, 0, 0, BLOCK_STATUS_VALID)
        
        # 只添加调整点附近的几个区块，而不是整个周期
        prev_hash = self.genesis_header.hash()
        # 添加ADJUSTMENT_INTERVAL - 2位置的区块
        pre_adjustment_header = BlockHeader(
            version=1,
            prev_block_hash=prev_hash,
            merkle_root=b'\x01'*32,
            timestamp=1234567890 + 1000,
            bits=INITIAL_BITS,
            nonce=2000
        )
        self.block_index.add_header(pre_adjustment_header, ADJUSTMENT_INTERVAL - 2, 100.0, 0, 100, BLOCK_STATUS_VALID)
        
        # 添加ADJUSTMENT_INTERVAL - 1位置的区块
        pre_adjustment_header2 = BlockHeader(
            version=1,
            prev_block_hash=pre_adjustment_header.hash(),
            merkle_root=b'\x02'*32,
            timestamp=1234567890 + 2000,
            bits=INITIAL_BITS,
            nonce=2001
        )
        self.block_index.add_header(pre_adjustment_header2, ADJUSTMENT_INTERVAL - 1, 101.0, 0, 200, BLOCK_STATUS_VALID)
        
        # # 计算非调整点的区块难度（例如ADJUSTMENT_INTERVAL + 2）
        # bits = self.block_index.calculate_required_bits(ADJUSTMENT_INTERVAL + 2)
        #
        # # 应该与前一个区块的难度相同
        # self.assertEqual(bits, INITIAL_BITS)

    def test_calculate_required_bits_at_adjustment_point(self):
        """测试在难度调整点的区块难度计算"""
        # 只添加计算难度调整所需的最少区块
        first_timestamp = 1234567890
        
        # 添加创世区块
        self.block_index.add_header(self.genesis_header, 0, 100.0, 0, 0, BLOCK_STATUS_VALID)
        
        # 添加第一个调整周期的第一个区块 (高度 ADJUSTMENT_INTERVAL - 1)
        first_in_period_header = BlockHeader(
            version=1,
            prev_block_hash=self.genesis_header.hash(),  # 这里简化处理，实际应该链接到前面的区块
            merkle_root=b'\x01'*32,
            timestamp=first_timestamp,
            bits=INITIAL_BITS,
            nonce=1000
        )
        self.block_index.add_header(first_in_period_header, ADJUSTMENT_INTERVAL - 1, 100.0, 0, 100, BLOCK_STATUS_VALID)
        
        # 添加第一个调整周期的最后一个区块 (高度 2 * ADJUSTMENT_INTERVAL - 1)
        last_in_period_header = BlockHeader(
            version=1,
            prev_block_hash=first_in_period_header.hash(),  # 这里简化处理
            merkle_root=b'\x02'*32,
            timestamp=first_timestamp + TARGET_TIMESPAN,  # 正好一个周期
            bits=INITIAL_BITS,
            nonce=2000
        )
        self.block_index.add_header(last_in_period_header, 2 * ADJUSTMENT_INTERVAL - 1, 200.0, 0, 200, BLOCK_STATUS_VALID)

        # 添加第一个调整周期的最后一个区块 (高度 2 * ADJUSTMENT_INTERVAL - 1)
        last_in_period_header = BlockHeader(
            version=1,
            prev_block_hash=first_in_period_header.hash(),  # 这里简化处理
            merkle_root=b'\x02' * 32,
            timestamp=first_timestamp + TARGET_TIMESPAN,  # 正好一个周期
            bits=INITIAL_BITS,
            nonce=2001
        )

        self.block_index.add_header(last_in_period_header, 2 * ADJUSTMENT_INTERVAL - 1, 200.0, 0, 200,
                                    BLOCK_STATUS_VALID)

        # # 计算调整点的区块难度（2 * ADJUSTMENT_INTERVAL）
        # bits = self.block_index.calculate_required_bits(2 * ADJUSTMENT_INTERVAL)
        #
        # # 应该返回与初始难度相同的值，因为时间间隔是理想的
        # self.assertEqual(bits, INITIAL_BITS)


if __name__ == '__main__':
    unittest.main()