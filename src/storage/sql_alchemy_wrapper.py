from sqlalchemy import create_engine, Column, Integer, String, LargeBinary, Float, Index
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.ext.declarative import declarative_base


# 先创建Base实例
Base = declarative_base()

class BlockHeaderModel(Base):
    __tablename__ = 'block_headers'

    block_hash = Column(LargeBinary(32), primary_key=True)
    prev_block_hash = Column(LargeBinary(32), nullable=False, index=True)
    merkle_root = Column(LargeBinary(32), nullable=False)
    timestamp = Column(Integer, nullable=False)
    bits = Column(Integer, nullable=False)
    nonce = Column(Integer, nullable=False)
    height = Column(Integer, nullable=False, index=True)
    total_work = Column(Float, nullable=False, index=True)
    status = Column(Integer, nullable=False)
    file_index = Column(Integer, nullable=False)
    file_offset = Column(Integer, nullable=False)

    # 添加索引
    __table_args__ = (
        Index('idx_prev_block_hash', 'prev_block_hash'),
    )

    def to_dict(self):
        """将模型实例转换为字典，方便使用。"""
        return {c.name: getattr(self, c.name) for c in self.__table__.columns}


class SQLAlchemyWrapper:
    """
    对SQLAlchemy的封装，处理SQLite的连接和会话管理。
    """


    def __init__(self, db_path: str):
        # connect_args={'check_same_thread': False} 是SQLite在多线程模式下所必需的
        self.engine = create_engine(f'sqlite:///{db_path}', connect_args={'check_same_thread': False})
        self.SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=self.engine)
        # Base是所有数据模型类的基类
        self.Base = Base

    def get_session(self) -> Session:
        """获取一个新的数据库会话。"""
        return self.SessionLocal()

    def create_all_tables(self):
        """根据所有继承自Base的模型类，创建数据库表。"""
        self.Base.metadata.create_all(self.engine)