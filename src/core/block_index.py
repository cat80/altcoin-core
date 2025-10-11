"""
block_index.py
负责维护区块头的索引。
这个重构后的版本使用 SQLAlchemy ORM 和全局的 sql_db 实例，
将数据库操作的底层细节完全分离出去。
"""
from typing import Optional, List, Tuple
from core.block_header import BlockHeader
from storage.sql_alchemy_wrapper import BlockHeaderModel
from storage.sql_alchemy_wrapper import SQLAlchemyWrapper
from config import *
from utils import bits_to_target,target_to_bits

class BlockIndex:
    """
    管理区块头索引。
    通过 SQLAlchemy ORM 与数据库交互。
    """
    sqldb :SQLAlchemyWrapper

    def __init__(self, sqldb :SQLAlchemyWrapper):
        # 不再需要直接管理数据库连接，
        self.sqldb = sqldb
        pass

    def add_header(self, header: BlockHeader, height: int, total_work: float, file_index: int, file_offset: int,status:int=BLOCK_STATUS_INVALID):
        """
        添加一个新的区块头到索引中。
        """
        with self.sqldb.get_session() as session:
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
                status= status,
                file_index=file_index,
                file_offset=file_offset
            )
            session.add(header_entry)
            session.commit()

    def get_header_info(self, block_hash: bytes) -> Optional[dict]:
        """
        根据哈希获取区块头的完整信息 (以dict形式)。
        """
        with self.sqldb.get_session() as session:
            header_model = session.query(BlockHeaderModel).filter_by(block_hash=block_hash).first()
            return header_model.to_dict() if header_model else None

    def get_genesis_block(self) -> Optional[dict]:
        """
        获取创世区块（高度为0的区块）的信息。
        """
        with self.sqldb.get_session() as session:
            genesis_model = session.query(BlockHeaderModel).filter_by(height=0).first()
            return genesis_model.to_dict() if genesis_model else None

    
    def get_tip(self) -> Optional[dict]:
        """
        获取当前已知拥有最大 total_work 的区块头信息，即主链的顶端。
        """
        with self.sqldb.get_session() as session:
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

    def find_common_ancestor(self, old_tip_hash: bytes, new_tip_hash: bytes) -> Tuple[Optional[bytes], List[dict], List[dict]]:
        """
        查找两个区块的共同祖先，并返回需要回滚的旧链区块列表和需要应用的新链区块列表。
        
        Returns:
            Tuple[Optional[bytes], List[dict], List[dict]]: 
            (共同祖先哈希, 需要回滚的旧链区块列表(从旧tip到共同祖先，不包括共同祖先), 
             需要应用的新链区块列表(从共同祖先到新tip，不包括共同祖先))
        """
        # 获取两个链的区块信息
        old_chain_blocks = []
        new_chain_blocks = []
        
        # 获取旧链区块信息，直到创世区块
        current_hash = old_tip_hash
        while current_hash:
            block_info = self.get_header_info(current_hash)
            if not block_info:
                break
            old_chain_blocks.append(block_info)
            current_hash = block_info['prev_block_hash']
        
        # 获取新链区块信息，直到创世区块或与旧链相遇
        current_hash = new_tip_hash
        new_chain_block_hashes = set()  # 用于快速查找共同祖先
        while current_hash:
            block_info = self.get_header_info(current_hash)
            if not block_info:
                break
            new_chain_blocks.append(block_info)
            new_chain_block_hashes.add(current_hash)
            # 检查是否在旧链中找到共同祖先
            if current_hash in [block['block_hash'] for block in old_chain_blocks]:
                break
            current_hash = block_info['prev_block_hash']
        
        # 查找共同祖先
        common_ancestor_hash = None
        for block_info in new_chain_blocks:
            if block_info['block_hash'] in [b['block_hash'] for b in old_chain_blocks]:
                common_ancestor_hash = block_info['block_hash']
                break
        
        if not common_ancestor_hash:
            # 如果没有找到共同祖先，返回None
            return None, [], []
        
        # 构造需要回滚的旧链区块列表（从旧tip到共同祖先，不包括共同祖先）
        old_chain_to_rollback = []
        for block_info in old_chain_blocks:
            if block_info['block_hash'] == common_ancestor_hash:
                break
            old_chain_to_rollback.append(block_info)
        
        # 构造需要应用的新链区块列表（从共同祖先到新tip，不包括共同祖先）
        new_chain_to_apply = []
        for block_info in reversed(new_chain_blocks):  # 反转列表以从共同祖先到新tip的顺序
            if block_info['block_hash'] == common_ancestor_hash:
                continue  # 跳过共同祖先
            new_chain_to_apply.append(block_info)
            if block_info['block_hash'] == new_tip_hash:
                break
        
        return common_ancestor_hash, old_chain_to_rollback, new_chain_to_apply

    def update_block_status(self, block_hash: bytes, status: int):
        """
        更新单个区块的状态。
        
        Args:
            block_hash: 区块哈希
            status: 新的状态值
        """
        with self.sqldb.get_session() as session:
            session.query(BlockHeaderModel).filter_by(block_hash=block_hash).update({"status": status})
            session.commit()

    def update_blocks_status(self, block_hashes: List[bytes], status: int):
        """
        批量更新多个区块的状态。
        
        Args:
            block_hashes: 区块哈希列表
            status: 新的状态值
        """
        if not block_hashes:
            return
            
        with self.sqldb.get_session() as session:
            session.query(BlockHeaderModel).filter(BlockHeaderModel.block_hash.in_(block_hashes)).update(
                {"status": status}, synchronize_session=False)
            session.commit()
            
    def get_header_by_height(self, height: int) -> Optional[dict]:
        """
        根据高度获取区块信息。
        
        Args:
            height: 区块高度
            
        Returns:
            Optional[dict]: 区块信息字典，如果找不到则返回None
        """
        with self.sqldb.get_session() as session:
            header_model = session.query(BlockHeaderModel).filter_by(height=height).first()
            return header_model.to_dict() if header_model else None

    def calculate_required_bits(self, new_block_height: int) -> int:
        """
        根据区块高度计算所需的难度(bits)。
        
        Args:
            new_block_height: 新区块的高度
            
        Returns:
            int: 计算出的bits值
        """
        # 1. 如果是创世区块或第一个周期的区块，使用初始bits
        if new_block_height < ADJUSTMENT_INTERVAL:
            return INITIAL_BITS

        # 2. 检查当前区块是否是难度调整点
        #    注意：是新周期的第一个区块需要调整，所以是对当前高度取余
        if new_block_height % ADJUSTMENT_INTERVAL != 0:
            # 如果不是调整点，难度与上一个区块相同
            previous_header = self.get_header_by_height(new_block_height - 1)
            return previous_header['bits']
        else:
            # 是难度调整点，需要计算新难度

            # a. 找到上一个周期的最后一个区块
            #    例如，计算高度20160的难度时，需要用20159的数据
            last_block_in_period = self.get_header_by_height(new_block_height - 1)

            # b. 找到上一个周期的第一个区块
            #    例如，计算高度20160的难度时，需要用10080的数据
            first_block_in_period = self.get_header_by_height(new_block_height - ADJUSTMENT_INTERVAL)

            # c. 计算实际花费时间
            actual_timespan = last_block_in_period['timestamp'] - first_block_in_period['timestamp']
            ONE_FOURTH_TIMESPAN = TARGET_TIMESPAN // 4
            FOUR_TIMES_TIMESPAN = TARGET_TIMESPAN * 4

            # d. 应用安全限制 (非常重要!)
            if actual_timespan < ONE_FOURTH_TIMESPAN:
                actual_timespan = ONE_FOURTH_TIMESPAN
            if actual_timespan > FOUR_TIMES_TIMESPAN:
                actual_timespan = FOUR_TIMES_TIMESPAN

            # e. 获取旧的Target值
            old_target = bits_to_target(last_block_in_period['bits'])

            # f. 使用核心公式计算新Target
            #    注意：为了避免浮点数精度问题，通常使用大整数运算
            new_target = old_target * actual_timespan // TARGET_TIMESPAN

            # # g. 确保新Target不超过网络允许的最大值 (初始Target)
            # if new_target > MAX_TARGET:
            #     new_target = MAX_TARGET

            # h. 将新Target转换回bits格式
            # 这里需要实现target_to_bits函数
            return target_to_bits(new_target)


    def close(self):
        pass