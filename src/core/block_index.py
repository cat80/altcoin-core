"""
block_index.py
负责维护区块头的索引。
这个重构后的版本使用 SQLAlchemy ORM 和全局的 sql_db 实例，
将数据库操作的底层细节完全分离出去。
"""
from typing import Optional

from core.block_header import BlockHeader
from storage.sql_alchemy_wrapper import BlockHeaderModel
from storage.sql_alchemy_wrapper import SQLAlchemyWrapper

# 定义区块状态的常量
STATUS_VALID = 1  # 表示区块头和内容都已完全验证
STATUS_INVALID = 0 # 表示区块已被验证为无效


class BlockIndex:
    """
    管理区块头索引。
    通过 SQLAlchemy ORM 与数据库交互。
    """
    def __init__(self,db:SQLAlchemyWrapper):
        # 不再需要直接管理数据库连接，
        self.db = db
        pass

    def add_header(self, header: BlockHeader, height: int, total_work: float, file_index: int, file_offset: int):
        """
        添加一个新的区块头到索引中。
        """
        with self.db.get_session() as session:
            block_hash = header.hash()
            header_entry = BlockHeaderModel(
                block_hash=block_hash,
                prev_block_hash=header.prev_block_hash,
                merkle_root=header.merkle_root,
                timestamp=header.timestamp,
                bits=header.bits,
                nonce=header.nonce,
                height=height,
                total_work=total_work,
                status=STATUS_VALID,
                file_index=file_index,
                file_offset=file_offset
            )
            session.add(header_entry)
            session.commit()

    def get_header_info(self, block_hash: bytes) -> Optional[dict]:
        """
        根据哈希获取区块头的完整信息 (以dict形式)。
        """
        with self.db.get_session() as session:
            header_model = session.query(BlockHeaderModel).filter_by(block_hash=block_hash).first()
            return header_model.to_dict() if header_model else None

    def get_tip(self) -> Optional[dict]:
        """
        获取当前已知拥有最大 total_work 的区块头信息，即主链的顶端。
        """
        with self.db.get_session() as session:
            tip_model = session.query(BlockHeaderModel).order_by(BlockHeaderModel.total_work.desc(), BlockHeaderModel.height.desc()).first()
            return tip_model.to_dict() if tip_model else None

    def get_ancestor(self, block_hash: bytes, height: int) -> Optional[dict]:
        """
        寻找一个区块的指定高度的祖先区块。
        """
        current_hash = block_hash
        while current_hash:
            info = self.get_header_info(current_hash)
            if not info:
                return None  # 链断裂
            if info['height'] == height:
                return info
            
            if info['height'] < height:
                return None  # 已过头
                
            current_hash = info['prev_block_hash']
        return None

    def close(self):
        pass