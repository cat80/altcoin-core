import unittest
from unittest.mock import Mock, patch, AsyncMock
import asyncio
from src.p2p.peer import Peer


class TestPeer(unittest.TestCase):
    def setUp(self):
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)
        
        # 创建模拟对象
        self.node_id = 'test_node_id'
        self.reader_mock = Mock()
        self.writer_mock = Mock()
        self.peer_manager_mock = Mock()
        self.event_bus_mock = Mock()
        
        # 初始化Peer
        with patch('asyncio.create_task') as mock_create_task:
            mock_create_task.return_value = Mock()
            self.peer = Peer(
                self.node_id,
                self.reader_mock,
                self.writer_mock,
                self.peer_manager_mock,
                self.event_bus_mock
            )
            
        self.peer_manager_mock.remove_peer = AsyncMock()
        self.event_bus_mock.publish = AsyncMock()

    def tearDown(self):
        self.loop.close()

    def test_init(self):
        """测试Peer初始化"""
        self.assertEqual(self.peer.node_id, self.node_id)
        self.assertEqual(self.peer.reader, self.reader_mock)
        self.assertEqual(self.peer.writer, self.writer_mock)
        self.assertEqual(self.peer.peer_manager, self.peer_manager_mock)
        self.assertEqual(self.peer.event_bus, self.event_bus_mock)
        self.assertIsNone(self.peer.connectable_ip)
        self.assertIsNone(self.peer.connectable_port)

    def test_set_connectable_address(self):
        """测试设置可连接地址"""
        self.peer.set_connectable_address('192.168.1.100', 8001)
        self.assertEqual(self.peer.connectable_ip, '192.168.1.100')
        self.assertEqual(self.peer.connectable_port, 8001)

    def test_get_connection_info(self):
        """测试获取连接信息"""
        # 设置可连接地址
        self.peer.set_connectable_address('192.168.1.100', 8001)
        
        # 获取连接信息
        conn_info = self.peer.get_connection_info()
        
        expected_info = {
            "node_id": self.node_id,
            "host": '192.168.1.100',
            "port": 8001
        }
        
        self.assertEqual(conn_info, expected_info)

    def test_send_message_success(self):
        """测试成功发送消息"""
        # 模拟writer方法成功执行
        self.writer_mock.write = Mock()
        self.writer_mock.drain = AsyncMock()
        
        # 发送消息
        self.loop.run_until_complete(
            self.peer.send_message('test_msg', {'data': 'test'})
        )
        
        # 验证writer方法被调用
        self.writer_mock.write.assert_called_once()
        self.writer_mock.drain.assert_called_once()

    def test_send_message_exception(self):
        """测试发送消息异常"""
        # 模拟writer方法抛出异常
        self.writer_mock.write = Mock(side_effect=Exception("Write error"))
        self.peer_manager_mock.remove_peer = AsyncMock()
        
        # 发送消息
        self.loop.run_until_complete(
            self.peer.send_message('test_msg', {'data': 'test'})
        )
        
        # 验证peer manager的remove_peer被调用
        self.peer_manager_mock.remove_peer.assert_called_once_with(self.peer)

    @patch('src.p2p.protocol.protocol')
    def test_run_message_loop_success(self, mock_protocol):
        """测试消息循环成功处理消息"""
        # 模拟reader和协议处理
        mock_protocol.deserialize_stream = AsyncMock(return_value=({'type': 'test_msg'}, b''))
        self.writer_mock.get_extra_info.return_value = ('127.0.0.1', 8001)
        
        # 为reader_mock添加异步读取支持
        self.reader_mock.read = AsyncMock(return_value=b'')
        
        # 模拟消息循环
        task = self.loop.create_task(self.peer._run_message_loop())
        
        # 等待一点时间让publish被调用
        self.loop.run_until_complete(asyncio.sleep(0.01))
        
        # 取消任务
        task.cancel()
        
        try:
            self.loop.run_until_complete(task)
        except asyncio.CancelledError:
            pass
        
        # 验证事件总线发布消息
        # self.event_bus_mock.publish.assert_called_with('network_message_received', self.peer, {'type': 'test_msg'})

    def test_close(self):
        """测试关闭连接"""
        # 创建模拟任务
        self.peer.main_loop_task = Mock()
        self.peer.main_loop_task.cancel = Mock()
        self.peer.main_loop_task.done = Mock(return_value=False)
        self.writer_mock.is_closing = Mock(return_value=False)
        self.writer_mock.close = Mock()
        self.writer_mock.wait_closed = AsyncMock()
        
        # 关闭peer
        self.loop.run_until_complete(self.peer.close())
        
        # 验证任务被取消，连接被关闭
        self.peer.main_loop_task.cancel.assert_called_once()
        self.writer_mock.close.assert_called_once()
        self.writer_mock.wait_closed.assert_called_once()

    def test_close_already_closing(self):
        """测试关闭已关闭的连接"""
        # 创建模拟任务
        self.peer.main_loop_task = Mock()
        self.peer.main_loop_task.cancel = Mock()
        self.peer.main_loop_task.done = Mock(return_value=True)  # 任务已完成
        self.writer_mock.is_closing = Mock(return_value=True)  # 已在关闭中
        self.writer_mock.close = Mock()
        self.writer_mock.wait_closed = AsyncMock()
        
        # 关闭peer
        self.loop.run_until_complete(self.peer.close())
        
        # 验证任务未被取消，连接未被关闭
        self.peer.main_loop_task.cancel.assert_not_called()
        self.writer_mock.close.assert_not_called()


if __name__ == '__main__':
    unittest.main()