"""
block_validator.py
包含所有关于区块和交易的共识验证规则。
这是一个无状态的模块，所有函数都应该是纯函数或静态方法，
不依赖于任何类实例的状态。
"""
import logging
from typing import List
from .block import Block
from .chain_state import ChainState
from .block_index import BlockIndex
from .block_header import BlockHeader
from utils.crypto import hash_data
from config import INITIAL_BLOCK_REWARD,REWARD_CUTOFF_BLOCKS
log = logging.getLogger(__name__)
from .transaction import Transaction

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
    def check_tx(transaction: Transaction, utxo_view: ChainState) -> bool:
        """
        验证单笔非Coinbase交易的有效性（主要用于Mempool）。
        - 检查UTXO是否存在。
        - 检查输入总额是否大于等于输出总额。
        - 验证交易签名。
        Args:
            transaction: 待验证的交易。
            utxo_view: 提供 get_utxo 方法的UTXO视图 (ChainState 或 ChainStateCacheView)。
        Returns:
            bool: 如果交易有效则返回 True，否则返回 False。
        """
        if transaction.is_coinbase():
            log.warning("check_tx should not be used for coinbase transactions.")
            return False

        try:
            # 1. 验证签名
            if not transaction.verify_signature():
                log.warning(f"Signature verification failed for transaction {transaction.hash().hex()}")
                return False

            # 2. 验证输入和输出
            input_sum = 0
            for tx_in in transaction.tx_ins:
                utxo = utxo_view.get_utxo(tx_in)
                if utxo is None:
                    log.warning(f"Input UTXO not found for transaction {transaction.hash().hex()}")
                    return False
                input_sum += utxo.value

            output_sum = sum(tx_out.value for tx_out in transaction.tx_outs)

            if input_sum < output_sum:
                log.warning(f"Input sum less than output sum in transaction {transaction.hash().hex()}")
                return False

        except Exception as e:
            log.error(f"Error during transaction check {transaction.hash().hex()}: {e}", exc_info=True)
            return False

        return True
    @staticmethod
    def check_non_coinbase_tx_and_get_fee(transactions: List['Transaction'], utxo_view):
        if not transactions:
            return 0
        total_fees = 0
        for tx in transactions:
            if tx.is_coinbase():
                raise ValueError('tx must be non-coinbase tx')
            input_sum = 0
            for tx_in in tx.tx_ins:
                utxo = utxo_view.get_utxo(tx_in)
                if utxo is None:
                    raise ValueError(f"Input UTXO not found for transaction {tx.hash().hex()}")
                input_sum += utxo.value

            output_sum = sum(tx_out.value for tx_out in tx.tx_outs)

            if input_sum < output_sum:
                raise ValueError(f"Input sum less than output sum in transaction {tx.hash().hex()}")

            total_fees += (input_sum - output_sum)

            # 验证交易签名 (假设verify_signature不需要UTXO信息，如果需要则需调整)
            if not tx.verify_signature():
                raise ValueError(f"Signature verification failed for transaction {tx.hash().hex()}")
        return total_fees
    @staticmethod
    def check_transactions_and_get_fees(transactions: List['Transaction'], utxo_view, block_height: int) -> int:
        """
        验证交易列表的UTXO有效性，并返回总交易费。
        这是一个通用的验证函数，可以接受任何提供get_utxo方法的对象。
        
        Args:
            transactions: 待验证的交易列表。
            utxo_view: 提供get_utxo方法的对象 (ChainState或ChainStateCacheView)。
            block_height: 当前区块的高度，用于计算区块奖励。
            
        Returns:
            int: 计算出的总交易费。
            
        Raises:
            ValueError: 如果验证失败。
        """
        if not transactions:
            raise ValueError("Transaction list cannot be empty.")

        if not transactions[0].is_coinbase():
            raise ValueError("First transaction must be a coinbase.")
            
        for tx in transactions[1:]:
            if tx.is_coinbase():
                raise ValueError("More than one coinbase transaction found.")

        # get all trans fee
        total_fees = BlockValidator.check_non_coinbase_tx_and_get_fee(transactions[1:],utxo_view)


        coinbase_tx = transactions[0]

        block_reward = BlockValidator.get_block_reward(block_height)
        coinbase_output_sum = sum(tx_out.value for tx_out in coinbase_tx.tx_outs)

        if coinbase_output_sum  != block_reward + total_fees:
            raise ValueError("Coinbase output value must equal block reward plus fees.")
        
        return total_fees

    @staticmethod
    def check_block(block: Block, utxo_view, block_index: BlockIndex, prev_header_info: dict) -> bool:
        """
        对一个新区块进行完整的、有状态的验证。
        """
        try:
            # 1. 验证默克尔根
            if not BlockValidator.check_merkle_root(block):
                log.debug("Validation failed: Merkle root mismatch.")
                return False
            
            # 2. 验证所有交易 (使用通用UTXO视图)
            block_height = prev_header_info['height'] + 1
            BlockValidator.check_transactions_and_get_fees(block.transactions, utxo_view, block_height)
            
        except ValueError as e:
            log.debug(f"Block validation failed: {e}", exc_info=True)
            return False
            
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
