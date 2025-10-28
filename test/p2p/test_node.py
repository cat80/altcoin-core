import unittest
from unittest.mock import Mock, patch, AsyncMock
import asyncio
from src.p2p.node import P2PNode


class TestP2PNode(unittest.TestCase):
    def setUp(self):
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)
        
        # 创建模拟对象
        self.peer_manager_mock = Mock()
        self.seed_nodes = [
            {'host': '127.0.0.1', 'port': 8001},
            {'host': '127.0.0.1', 'port': 8002}
        ]
        
        # 初始化P2PNode
        self.node = P2PNode(self.peer_manager_mock, self.seed_nodes)

    def tearDown(self):
        self.loop.close()

    def test_init(self):
        """测试P2PNode初始化"""
        self.assertEqual(self.node.peer_manager, self.peer_manager_mock)
        self.assertEqual(self.node.seed_nodes, self.seed_nodes)
        self.assertIsNone(self.node.server)


    @patch('asyncio.open_connection')
    def test_initiate_outgoing_connection_success(self, mock_open_connection):
        """测试发起外部连接成功"""
        # 模拟连接成功
        mock_reader = Mock()
        mock_writer = Mock()
        mock_open_connection.return_value = (mock_reader, mock_writer)
        mock_writer.get_extra_info.return_value = ('127.0.0.1', 8001)
        
        # 模拟peer manager握手
        self.peer_manager_mock.start_handshake = AsyncMock()
        
        # 发起连接
        self.loop.run_until_complete(
            self.node.initiate_outgoing_connection('127.0.0.1', 8001)
        )
        
        # 验证连接和握手
        mock_open_connection.assert_called_once_with('127.0.0.1', 8001)
        self.peer_manager_mock.start_handshake.assert_called_once_with(
            mock_reader, mock_writer, is_initiator=True
        )

    @patch('asyncio.open_connection')
    def test_initiate_outgoing_connection_failure(self, mock_open_connection):
        """测试发起外部连接失败"""
        # 模拟连接失败
        mock_open_connection.side_effect = Exception("Connection failed")
        
        # 模拟peer manager方法存在
        self.peer_manager_mock.start_handshake = AsyncMock()
        

    @patch('src.p2p.peer_manager.PeerManager')
    def test_on_incoming_connection(self, mock_peer_manager_class):
        """测试处理传入连接"""
        # 创建模拟reader/writer
        mock_reader = Mock()
        mock_writer = Mock()
        mock_writer.get_extra_info.return_value = ('127.0.0.1', 8001)
        
        # 模拟peer manager握手
        self.peer_manager_mock.start_handshake = AsyncMock()

if __name__ == '__main__':
    unittest.main()