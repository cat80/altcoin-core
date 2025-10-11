"""
block_validator.py
包含所有关于区块和交易的共识验证规则。
这是一个无状态的模块，所有函数都应该是纯函数或静态方法，
不依赖于任何类实例的状态。
"""
from .block import Block
from .chain_state import ChainState
from .block_index import BlockIndex
from .block_header import BlockHeader
from utils.crypto import hash_data
from config import INITIAL_BLOCK_REWARD,REWARD_CUTOFF_BLOCKS

class BlockValidator:
    """
    一个封装所有共识验证逻辑的命名空间。
    所有方法都设为静态方法，因为它不管理任何状态。
    """
    
    @staticmethod
    def check_block_header(header: BlockHeader) -> bool:
        """
        验证区块头自身的合法性 (PoW)。
        """
        target = BlockValidator.bits_to_target(header.bits)
        block_hash = header.hash()
        return int.from_bytes(block_hash, 'big') < target

    @staticmethod
    def check_merkle_root(block: Block) -> bool:
        """
        验证区块头中的默克尔根是否与交易列表匹配。
        """
        from utils import MerkleTree
        tx_hashes = [tx.hash() for tx in block.transactions]
        merkle_root = MerkleTree(tx_hashes).root
        return merkle_root == block.header.merkle_root

    @staticmethod
    def check_block_transactions(block: Block, chain_state: ChainState, block_height: int) -> bool:
        """
        验证区块内所有交易的合法性。
        这是最复杂和最关键的验证部分。
        """
        if not block.transactions:
            return False

        # 1. 检查第一笔交易必须是Coinbase
        if not block.transactions[0].is_coinbase():
            return False
            
        # 2. 检查除了第一笔之外没有其他Coinbase
        for tx in block.transactions[1:]:
            if tx.is_coinbase():
                return False

        total_fees = 0
        # 3. 逐个验证所有交易
        for tx in block.transactions:
            if not tx.is_coinbase():
                # 3.1 验证非Coinbase交易
                input_sum = 0
                for tx_in in tx.tx_ins:
                    utxo = chain_state.get_utxo(tx_in)
                    if utxo is None:
                        # 输入的UTXO不存在
                        return False
                    input_sum += utxo.value
                
                output_sum = sum(tx_out.value for tx_out in tx.tx_outs)
                
                if input_sum < output_sum:
                    # 输入总额必须大于等于输出总额
                    return False
                
                total_fees += (input_sum - output_sum)
                
                # 3.2 验证交易签名
                if not tx.verify_signature():
                    return False
            else:
                # 3.3 验证Coinbase交易
                # 检查Coinbase的输出总额是否超过了区块奖励+交易费
                block_reward = BlockValidator.get_block_reward(block_height)
                coinbase_output_sum = sum(tx_out.value for tx_out in tx.tx_outs)
                if coinbase_output_sum > block_reward + total_fees:
                    return False
        
        return True

    @staticmethod
    def check_block(block: Block, chain_state: ChainState, block_index: BlockIndex, prev_header_info: dict) -> bool:
        """
        对一个新区块进行完整的、有状态的验证。
        这是在尝试将区块连接到主链之前调用的总入口。
        """
        # 1. 验证默克尔根
        if not BlockValidator.check_merkle_root(block):
            print("Validation failed: Merkle root mismatch.")
            return False
            
        # 2. 验证所有交易
        block_height = prev_header_info['height'] + 1
        if not BlockValidator.check_block_transactions(block, chain_state, block_height):
            print("Validation failed: Transaction checks failed.")
            return False
            
        # 可以在这里添加更多检查，例如时间戳是否合理等
        
        return True

    @staticmethod
    def bits_to_target(bits: int) -> int:
        """
            将区块头中的bits字段转换为一个大的整数目标值。
            cat80 add:
                这里有一个核心的难度存储问题：bits是四个字节的整数，在block_header里面是小端存储的。成功序列化为整数后。
                bits的大端如：0x1d00ffff,第一个字节代表左移的量这里是,后三个字节组成的大端整数，则代表基础的难难度。exponent-3个字节的原因是位置的原始数据已经包含了三个字节。可以简单的计算如果bits为0x200ffff,则意味着每16次就能挖到矿一次。难度调节也是根据前N个区块的时间差，与预期的时间比较，动态的上调或者下调难度
        """
        exponent = bits >> 24
        mantissa = bits & 0x00ffffff
        # target = mantissa * (2 ** (8 * (exponent - 3)))
        # 采用更为直观的位移法
        move_left = (exponent-3)*8
        target = mantissa << move_left
        return target

    @staticmethod
    def get_block_reward(height: int) -> int:
        """
            根据区块高度计算区块奖励。
        """
        halvings = height // REWARD_CUTOFF_BLOCKS
        reward = INITIAL_BLOCK_REWARD >> halvings
        return  reward if reward > 0 else 0
