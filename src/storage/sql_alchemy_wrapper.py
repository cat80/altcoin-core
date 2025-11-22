from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session

class SQLAlchemyWrapper:
    """
    一个通用的 SQLAlchemy 封装类，处理数据库连接和会话管理。
    它通过依赖注入的方式接收一个 Base，从而可以为任何数据库服务。
    """

    def __init__(self, db_path: str):
        """
        :param db_path: 数据库文件的路径。
        """
        # connect_args={'check_same_thread': False} 是 SQLite 在多线程模式下所必需的
        self.engine = create_engine(f'sqlite:///{db_path}', connect_args={'check_same_thread': False})
        self.SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=self.engine)

    def get_session(self) -> Session:
        """获取一个新的数据库会话。"""
        return self.SessionLocal()

    def create_all_tables(self, base):
        """
        根据传入的 Base 对象，创建所有相关的数据库表。
        :param base: 从 declarative_base() 返回的 Base 实例。
        """
        base.metadata.create_all(self.engine, checkfirst=True)

    def close(self):
        """关闭数据库引擎连接，释放所有连接池中的连接。"""
        self.engine.dispose()
