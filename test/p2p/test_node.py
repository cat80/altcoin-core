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
        
        # 初始化P2PNode
        self.node = P2PNode(self.peer_manager_mock)

    def tearDown(self):
        self.loop.close()

    def test_init(self):
        """测试P2PNode初始化"""
        self.assertEqual(self.node.peer_manager, self.peer_manager_mock)
        self.assertIsNone(self.node.server)

    @patch('asyncio.start_server')
    def test_start(self, mock_start_server):
        """测试启动节点服务器"""
        mock_server = Mock()
        # 为mock_server添加异步上下文管理器支持
        mock_server.__aenter__ = AsyncMock(return_value=mock_server)
        mock_server.__aexit__ = AsyncMock(return_value=None)
        mock_server.serve_forever = AsyncMock()
        
        mock_start_server.return_value = mock_server
        
        # 启动节点
        task = self.loop.create_task(
            self.node.start('127.0.0.1', 8001)
        )
        
        # 等待一点时间让start_server被调用
        self.loop.run_until_complete(asyncio.sleep(0.01))
        
        # 取消任务以退出无限循环
        task.cancel()
        
        try:
            self.loop.run_until_complete(task)
        except asyncio.CancelledError:
            pass
        
        # 验证服务器已启动
        mock_start_server.assert_called_once_with(
            self.node.on_incoming_connection, '127.0.0.1', 8001
        )

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
        mock_open_connection.side_effect = ConnectionRefusedError("Connection refused")
        
        # 模拟peer manager方法存在
        self.peer_manager_mock.start_handshake = AsyncMock()
        self.peer_manager_mock.event_bus = Mock()
        self.peer_manager_mock.event_bus.publish = AsyncMock()
        
        # 发起连接
        self.loop.run_until_complete(
            self.node.initiate_outgoing_connection('127.0.0.1', 8001, 'test_node_id')
        )
        
        # 验证连接尝试和事件发布
        mock_open_connection.assert_called_once_with('127.0.0.1', 8001)
        self.peer_manager_mock.event_bus.publish.assert_called_once_with('peer_connection_failed', 'test_node_id')

    def test_on_incoming_connection(self):
        """测试处理传入连接"""
        # 创建模拟reader/writer
        mock_reader = Mock()
        mock_writer = Mock()
        mock_writer.get_extra_info.return_value = ('127.0.0.1', 8001)
        
        # 模拟peer manager握手
        self.peer_manager_mock.start_handshake = AsyncMock()
        
        # 处理传入连接
        self.loop.run_until_complete(
            self.node.on_incoming_connection(mock_reader, mock_writer)
        )
        
        # 验证peer manager握手被调用
        self.peer_manager_mock.start_handshake.assert_called_once_with(
            mock_reader, mock_writer, is_initiator=False
        )

if __name__ == '__main__':
    unittest.main()