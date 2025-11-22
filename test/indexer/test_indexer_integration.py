import os
import shutil

from indexer.block_indexer import BlockIndexer
from storage.sql_alchemy_wrapper import SQLAlchemyWrapper
from core.blockchain import Blockchain
from indexer.model import IndexerState, AddressUTXO, BlockInfo, AddressTransaction
from config import INITIAL_BLOCK_REWARD,setup_logging
from indexer.block_indexer import BlockIndexer
import unittest
class TestBlockIndexerIntegration(unittest.TestCase):
    """
    测试 BlockIndexer 在真实区块链环境下的集成。
    """

    def setUp(self):
        """为每个同步测试设置真实的环境。"""
        # 使用 abspath 来解析路径，避免 '..' 造成的问题
        base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
        self.node_data_dir = os.path.join(base_dir, "nodes-data", "node17880-test")
        self.db_path = os.path.join(self.node_data_dir, "indexer_test.db")

        self.db_path = os.path.join(self.node_data_dir, "indexer_test.db")

        self.db_wrapper = SQLAlchemyWrapper(self.db_path)
        self.blockchain = Blockchain.new_from_data_dir(self.node_data_dir)

        self.indexer = BlockIndexer(self.db_wrapper, self.blockchain)

    def tearDown(self):
        """清理测试产生的文件。"""
        pass

    def test_address_transaction_value_on_spend(self):
        pass
        # self.indexer.sync_to_chain()
        # 这个测试用例旨在验证当一个地址消费一笔 UTXO 时，其 value 字段是否被正确处理
        # 具体的测试逻辑需要根据你的 AddressTransaction 表结构和需求来填写
        # 例如，你可以触发一个区块同步，然后查询数据库来验证数据
        pass
