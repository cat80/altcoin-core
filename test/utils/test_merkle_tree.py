import unittest
import sys
import os

from utils.merkle_tree import MerkleTree
from utils.crypto import hash_data


class TestMerkleTree(unittest.TestCase):
    
    def test_single_leaf_tree(self):
        """测试只有一个叶子节点的默克尔树"""
        leaf = hash_data(b"leaf1")
        leaves = [leaf]
        tree = MerkleTree(leaves)
        
        # 根节点应该等于唯一的叶子节点
        self.assertEqual(tree.root, leaf)

        
        # 验证不同叶子列表
        other_leaf = hash_data(b"other")
        self.assertFalse(tree.verify(other_leaf))

    def test_two_leaves_tree(self):
        """测试有两个叶子节点的默克尔树"""
        leaves = []

        for i in range(10):
            leaves.append(hash_data(b'leaf'+i.to_bytes()))
        markle_tree = MerkleTree(leaves)
        root = markle_tree.root
        markle_tree1 = MerkleTree(leaves)
        self.assertTrue(markle_tree1.verify(root))

    def test_three_leaves_tree(self):
        """测试有三个叶子节点的默克尔树"""
        leaf1 = hash_data(b"leaf1")
        leaf2 = hash_data(b"leaf2")
        leaf3 = hash_data(b"leaf3")
        leaves = [leaf1, leaf2, leaf3]
        tree = MerkleTree(leaves)
        
        # 手动计算根节点
        # 第二层节点
        parent1 = hash_data(leaf1 + leaf2)  # 左右配对
        parent2 = hash_data(leaf3 + leaf3)  # 奇数个节点复制最后一个
        
        # 根节点
        expected_root = hash_data(parent1 + parent2)
        self.assertEqual(tree.root, expected_root)

        
        # 验证不同的叶子列表应该失败
        other_leaf = hash_data(b"other")
        self.assertFalse(tree.verify(other_leaf))

    def test_four_leaves_tree(self):
        """测试有四个叶子节点的默克尔树"""
        leaf1 = hash_data(b"leaf1")
        leaf2 = hash_data(b"leaf2")
        leaf3 = hash_data(b"leaf3")
        leaf4 = hash_data(b"leaf4")
        leaves = [leaf1, leaf2, leaf3, leaf4]
        tree = MerkleTree(leaves)
        
        # 手动计算根节点
        # 第二层节点
        parent1 = hash_data(leaf1 + leaf2)
        parent2 = hash_data(leaf3 + leaf4)
        
        # 根节点
        expected_root = hash_data(parent1 + parent2)
        self.assertEqual(tree.root, expected_root)


    def test_empty_tree(self):
        """测试空的默克尔树"""
        tree = MerkleTree([])
        
        # 空树的根节点应该是None
        self.assertIsNone(tree.root)

        # 验证非空列表应该失败
        leaf = hash_data(b"leaf")
        self.assertFalse(tree.verify(leaf))


if __name__ == '__main__':
    unittest.main()