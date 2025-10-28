"""
Storage module for Altcoin.
Contains database and file storage functionality.
"""
import logging

log = logging.getLogger(__name__)
from storage.rocksdb_wrapper import RocksDBWrapper
from storage.sql_alchemy_wrapper import SQLAlchemyWrapper

from config import Config
# 1. 创建全局RocksDB访问对象
_utxo_db_instance = None # 私有变量，存储实例
def get_utxo_db(config:Config):
    global _utxo_db_instance
    if _utxo_db_instance is None:
        _utxo_db_instance = RocksDBWrapper(config.rocksdb_dir)
        log.info("RocksDB connection established.")
    return _utxo_db_instance

# 创建全局的sql访问
__sql_db = None
def get_sql_db():
    global __sql_db
    if not __sql_db:
        __sql_db = SQLAlchemyWrapper(config.sqlite_path)
        log.info("SQLAlchemy (SQLite) connection established.")
        # 自动创建所有定义的ORM模型对应的表
        __sql_db.create_all_tables()

    return __sql_db