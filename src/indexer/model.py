from sqlalchemy import Column, Integer, TEXT, BIGINT
from sqlalchemy.ext.declarative import declarative_base

# 为 indexer 数据库定义一个独立的 Base。
Base = declarative_base()

class IndexerState(Base):
    """
    用于记录索引器自身的状态，例如最后索引的区块高度。
    """
    __tablename__ = 'indexer_state'
    key = Column(TEXT, primary_key=True)
    value = Column(TEXT, nullable=False)

class BlockInfo(Base):
    """
    存储每个区块的摘要信息。
    """
    __tablename__ = 'blocks'
    height = Column(Integer, primary_key=True)
    hash = Column(TEXT, unique=True, nullable=False, index=True)
    prev_hash = Column(TEXT, nullable=False)
    merkle_root = Column(TEXT, nullable=False)
    timestamp = Column(Integer, nullable=False)
    tx_count = Column(Integer, nullable=False)

class TransactionInfo(Base):
    """
    存储每笔交易的摘要信息。
    """
    __tablename__ = 'transactions'
    tx_hash = Column(TEXT, primary_key=True)
    block_hash = Column(TEXT, nullable=False, index=True)
    block_height = Column(Integer, nullable=False, index=True)
    fee = Column(BIGINT, nullable=False)
    timestamp = Column(Integer, nullable=False)

class AddressUTXO(Base):
    """
    用于索引每个地址拥有的UTXO。
    """
    __tablename__ = 'address_utxos'
    id = Column(Integer, primary_key=True, autoincrement=True)
    tx_hash = Column(TEXT, nullable=False, index=True)
    output_index = Column(Integer, nullable=False)
    address = Column(TEXT, nullable=False, index=True)
    value = Column(BIGINT, nullable=False)
    block_height = Column(Integer, nullable=False)

class AddressTransaction(Base):
    """
    地址与交易的关联表，用于快速查询某个地址的所有相关交易。
    """
    __tablename__ = 'address_transactions'
    id = Column(Integer, primary_key=True, autoincrement=True)
    address = Column(TEXT, nullable=False, index=True)
    tx_hash = Column(TEXT, nullable=False, index=True)
    block_height = Column(Integer, nullable=False)
    # 'input' 或 'output'，表示该地址在此交易中是作为输入方还是输出方
    role = Column(TEXT, nullable=False)
    # 关键补充：记录这笔输入/输出的金额。
    # 正数表示收入 (output)，负数表示支出 (input)。
    value = Column(BIGINT, nullable=False)
