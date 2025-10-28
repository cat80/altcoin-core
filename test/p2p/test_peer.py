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

    def test_close(self):
        """测试关闭连接"""
        # 创建模拟任务
        self.peer.main_loop_task = Mock()
        self.peer.main_loop_task.cancel = Mock()
        self.writer_mock.is_closing = Mock(return_value=False)
        self.writer_mock.close = Mock()
        self.writer_mock.wait_closed = AsyncMock()
        
        # 关闭peer
        self.loop.run_until_complete(self.peer.close())
        
        # 验证任务被取消，连接被关闭
        self.peer.main_loop_task.cancel.assert_called_once()
        self.writer_mock.close.assert_called_once()
        self.writer_mock.wait_closed.assert_called_once()


if __name__ == '__main__':
    unittest.main()