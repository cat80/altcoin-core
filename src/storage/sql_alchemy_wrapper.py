from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.ext.declarative import declarative_base


class SQLAlchemyWrapper:
    """
    对SQLAlchemy的封装，处理SQLite的连接和会话管理。
    """

    def __init__(self, db_path: str):
        # connect_args={'check_same_thread': False} 是SQLite在多线程模式下所必需的
        self.engine = create_engine(f'sqlite:///{db_path}', connect_args={'check_same_thread': False})
        self.SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=self.engine)
        # Base是所有数据模型类的基类
        self.Base = declarative_base()

    def get_session(self) -> Session:
        """获取一个新的数据库会话。"""
        return self.SessionLocal()

    def create_all_tables(self):
        """根据所有继承自Base的模型类，创建数据库表。"""
        self.Base.metadata.create_all(self.engine)