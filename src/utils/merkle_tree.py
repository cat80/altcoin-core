import hashlib
from typing import List
from .crypto import hash_data


class MerkleTree:
    """
    一个简单的默克尔树实现。
    """

    def __init__(self, leaves: List[bytes]):
        """
        根据叶子节点（交易哈希列表）构建默克尔树。
        :param leaves: 交易哈希的列表。
        """
        self.leaves = leaves
        self.tree = self._build_tree()

    def _build_tree(self) -> List[List[bytes]]:
        if not self.leaves:
            return []
        tree = [self.leaves]
        current_level = self.leaves

        while len(current_level) > 1:
            next_level = []
            # 将当前层两两配对计算哈希
            for i in range(0, len(current_level), 2):
                left = current_level[i]
                # 如果是奇数个节点，就复制最后一个
                right = current_level[i + 1] if i + 1 < len(current_level) else left

                # 注意：比特币中会反转字节序，我们这里为了简化，直接拼接
                parent_hash = hash_data(left + right)
                next_level.append(parent_hash)

            tree.append(next_level)
            current_level = next_level

        return tree

    @property
    def root(self) -> bytes:
        """返回默克尔树的根哈希。"""
        return self.tree[-1][0] if self.tree else None

    def verify(self, root : bytes) -> bool:
        """
        验证给定的叶子节点列表是否与当前默克尔树根哈希一致。
        
        :param leaves: 需要验证的叶子节点列表
        :return: 如果一致返回True，否则返回False
        """
        return root == self.root