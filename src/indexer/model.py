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
    timestamp = Column(Integer, nullable=False, index=True)
    tx_count = Column(Integer, nullable=False)
    block_minner = Column(TEXT, default='')
    
    # 新增字段
    size = Column(Integer, nullable=False)  # 区块大小(bytes)
    bits = Column(Integer, nullable=False)
    nonce = Column(BIGINT, nullable=False)
    block_reward = Column(BIGINT, nullable=False)  # 块奖励
    total_fee = Column(BIGINT, nullable=False)  # 手续费
    total_reward = Column(BIGINT, nullable=False)  # 总奖励 = block_reward + total_fee
    total_tx_amount = Column(BIGINT, nullable=False)  # 交易数额(tinyalt)

class TransactionInfo(Base):
    """
    存储每笔交易的摘要信息。
    """
    __tablename__ = 'transactions'
    hash = Column(TEXT, primary_key=True)
    block_hash = Column(TEXT, nullable=False, index=True)
    block_height = Column(Integer, nullable=False, index=True)
    timestamp = Column(Integer, nullable=False, index=True)
    
    # 新增和调整的字段
    tx_index = Column(Integer, nullable=False)  # 交易在区块中的索引
    fee = Column(BIGINT, nullable=False)  # 手续费
    input_amount = Column(BIGINT, nullable=False)  # 输入总金额
    output_amount = Column(BIGINT, nullable=False)  # 输出总金额
    tx_amount = Column(BIGINT, nullable=False)  # 交易金额 (input_amount - change)
    input_count = Column(Integer, nullable=False)  # 输入笔数
    output_count = Column(Integer, nullable=False)  # 输出笔数
    op_return_data = Column(TEXT)  # OP_RETURN 数据 (hex)

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
    block_height = Column(Integer, nullable=False, index=True)
    timestamp = Column(Integer, nullable=False, index=True)
    # 'input' 或 'output'，表示该地址在此交易中是作为输入方还是输出方
    role = Column(TEXT, nullable=False)
    # 关键补充：记录这笔输入/输出的金额。
    # 正数表示收入 (output)，负数表示支出 (input)。
    value = Column(BIGINT, nullable=False)
    
    # 新增字段，仅对 role='input' 有意义，用于追踪资金来源
    prev_tx_hash = Column(TEXT, index=True)
    prev_tx_out_index = Column(Integer)
