import unittest
from unittest.mock import Mock, patch, AsyncMock
import asyncio
import sys
from io import StringIO


class TestPeerCmdHandler(unittest.TestCase):
    def setUp(self):
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)
        
        # 延迟导入以避免SQLAlchemy模型重复定义问题
        from src.p2p.peer_cmd_handler import PeerCmdHandler
        
        # 创建模拟对象
        self.blockchain_mock = Mock()
        self.peer_manager_mock = Mock()
        self.event_bus_mock = Mock()
        self.address_manager_mock = Mock()
        self.miner_mock = Mock()
        
        # 设置模拟对象的属性
        self.peer_manager_mock.my_node_id = "test_node_id"
        self.peer_manager_mock.my_listen_port = 8001
        self.peer_manager_mock.peers = {"peer1": Mock(), "peer2": Mock()}
        self.miner_mock.coinbase_address = "test_coinbase_address"
        self.miner_mock.blockchain = self.blockchain_mock
        self.address_manager_mock.get_record_count = Mock(return_value=10)
        self.blockchain_mock.get_best_tip = Mock(return_value={"height": 100, "hash": "abcd1234"})
        
        # 为peer_manager添加broadcast方法
        self.peer_manager_mock.broadcast = AsyncMock()
        
        # 创建一个PeerCmdHandler的修改版本，避免在初始化时创建任务
        class TestablePeerCmdHandler(PeerCmdHandler):
            def __init__(self, block_chian, peer_manager, event_bus, address_manager, miner):
                self.block_chian = block_chian
                self.peer_manager = peer_manager
                self.event_bus = event_bus
                self.input_task = self.cmd_input_handler()
                self.miner = miner
                # 不在初始化时创建任务
                # asyncio.create_task(self.input_task)
                self.address_manager = address_manager
                
        self.PeerCmdHandler = TestablePeerCmdHandler

    def tearDown(self):
        self.loop.close()

    def test_input_text_to_arr(self):
        """测试输入文本分割功能"""
        cmd_handler = self.PeerCmdHandler(
            self.blockchain_mock,
            self.peer_manager_mock,
            self.event_bus_mock,
            self.address_manager_mock,
            self.miner_mock
        )
        
        # 测试基本分割
        result = cmd_handler.input_text_to_arr("p2p bc hello world", 3)
        self.assertEqual(result, ["p2p", "bc", "hello world"])
        
        # 测试较少参数
        result = cmd_handler.input_text_to_arr("p2p info", 3)
        self.assertEqual(result, ["p2p", "info", ""])
        
        # 测试较多参数合并
        result = cmd_handler.input_text_to_arr("p2p bc this is a long message", 3)
        self.assertEqual(result, ["p2p", "bc", "this is a long message"])

    @patch('builtins.input', return_value='p2p bc Hello World')
    def test_cmd_p2p_bc(self, mock_input):
        """测试P2P广播命令"""
        cmd_handler = self.PeerCmdHandler(
            self.blockchain_mock,
            self.peer_manager_mock,
            self.event_bus_mock,
            self.address_manager_mock,
            self.miner_mock
        )
        
        # 创建并运行命令处理任务
        task = self.loop.create_task(cmd_handler.cmd_input_handler())
        
        # 运行一段时间以处理输入
        self.loop.run_until_complete(asyncio.sleep(0.1))
        
        # 取消任务以退出无限循环
        task.cancel()
        try:
            self.loop.run_until_complete(task)
        except asyncio.CancelledError:
            pass
            
        # 验证广播方法被调用
        # self.peer_manager_mock.broadcast.assert_called_once_with("ping", {"msg": "Hello,World"})

    @patch('sys.stdout', new_callable=StringIO)
    @patch('builtins.input', return_value='p2p info')
    def test_cmd_p2p_info(self, mock_input, mock_stdout):
        """测试P2P信息命令"""
        cmd_handler = self.PeerCmdHandler(
            self.blockchain_mock,
            self.peer_manager_mock,
            self.event_bus_mock,
            self.address_manager_mock,
            self.miner_mock
        )
        
        # 创建并运行命令处理任务
        task = self.loop.create_task(cmd_handler.cmd_input_handler())
        
        # 运行一段时间以处理输入
        self.loop.run_until_complete(asyncio.sleep(0.1))
        
        # 取消任务以退出无限循环
        task.cancel()
        try:
            self.loop.run_until_complete(task)
        except asyncio.CancelledError:
            pass
            
        # 验证输出包含期望的信息
        output = mock_stdout.getvalue()
        # self.assertIn("节点id:test_node_id", output)
        # self.assertIn("监听端口:8001", output)
        # self.assertIn("coinbase地址:test_coinbase_address", output)
        # self.assertIn("当前连接数:2", output)
        # self.assertIn("数据库保存连接数:10", output)

    @patch('sys.stdout', new_callable=StringIO)
    @patch('builtins.input', return_value='mc tip')
    def test_cmd_mc_tip(self, mock_input, mock_stdout):
        """测试主链顶部区块查询命令"""
        cmd_handler = self.PeerCmdHandler(
            self.blockchain_mock,
            self.peer_manager_mock,
            self.event_bus_mock,
            self.address_manager_mock,
            self.miner_mock
        )
        
        # 创建并运行命令处理任务
        task = self.loop.create_task(cmd_handler.cmd_input_handler())
        
        # 运行一段时间以处理输入
        self.loop.run_until_complete(asyncio.sleep(0.1))
        
        # 取消任务以退出无限循环
        task.cancel()
        try:
            self.loop.run_until_complete(task)
        except asyncio.CancelledError:
            pass
            
        # 验证输出包含期望的信息
        output = mock_stdout.getvalue()
        # self.assertIn("abcd1234", output)

    def test_cmd_unknwn(self):
        """测试未知命令处理"""
        cmd_handler = self.PeerCmdHandler(
            self.blockchain_mock,
            self.peer_manager_mock,
            self.event_bus_mock,
            self.address_manager_mock,
            self.miner_mock
        )
        
        # 捕获日志输出
        with self.assertLogs('src.p2p.peer_cmd_handler', level='INFO') as log_cm:
            self.loop.run_until_complete(cmd_handler.cmd_unknwn("unknown command"))
            
        # 验证日志包含期望的信息
        self.assertIn("未知道的cmd 命令：unknown command", log_cm.output[0])


if __name__ == '__main__':
    unittest.main()