from sqlalchemy import Column, Integer, LargeBinary
from sqlalchemy.ext.declarative import declarative_base

# 为 Blockchain 核心数据库 (index.db) 定义一个独立的 Base
CoreBase = declarative_base()

class BlockHeaderModel(CoreBase):
    __tablename__ = 'block_headers'

    block_hash = Column(LargeBinary(32), primary_key=True)
    prev_block_hash = Column(LargeBinary(32), nullable=False, index=True)
    merkle_root = Column(LargeBinary(32), nullable=False)
    timestamp = Column(Integer, nullable=False)
    version = Column(Integer, nullable=False, default=1)
    bits = Column(Integer, nullable=False)
    nonce = Column(Integer, nullable=False)
    height = Column(Integer, nullable=False, index=True)
    total_work = Column(Integer, nullable=False, index=True)
    status = Column(Integer, nullable=False)
    file_index = Column(Integer, nullable=False)
    file_offset = Column(Integer, nullable=False)

    def to_dict(self):
        """将模型实例转换为字典，方便使用。"""
        return {c.name: getattr(self, c.name) for c in self.__table__.columns}
