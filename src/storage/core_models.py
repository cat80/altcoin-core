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


class UndoRecordModel(CoreBase):
    """
    新增：用于记录区块回滚所需信息的“撤销记录”。
    当一个区块被应用时，它所花费的每一个UTXO都会在这里被记录下来。
    """
    __tablename__ = 'undo_records'

    id = Column(Integer, primary_key=True, autoincrement=True)

    # 这个UTXO是被哪个区块花掉的
    block_hash = Column(LargeBinary(32), nullable=False, index=True)

    # --- 以下是重建被花费的那个UTXO (TxOut) 所需的完整信息 ---

    # 创建这个UTXO的交易哈希
    prev_tx_hash = Column(LargeBinary(32), nullable=False)
    # 这个UTXO在创建它的交易中的输出索引
    prev_tx_out_index = Column(Integer, nullable=False)
    # 金额
    value = Column(Integer, nullable=False)
    # 锁定脚本 (地址)
    locking_script = Column(LargeBinary, nullable=False)
