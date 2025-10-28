import unittest
from unittest.mock import Mock, patch, AsyncMock
import asyncio
from src.p2p.peer_manager import PeerManager
from src.p2p.peer import Peer


class TestPeerManager(unittest.TestCase):
    def setUp(self):
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)
        
        # 创建模拟对象
        self.event_bus_mock = Mock()
        self.peer_manager = PeerManager(self.event_bus_mock, 'my_node_id')
        
        # 添加模拟方法
        self.event_bus_mock.subscribe = Mock()
        self.event_bus_mock.publish = AsyncMock()

    def tearDown(self):
        self.loop.close()

    def test_init(self):
        """测试PeerManager初始化"""
        self.assertEqual(self.peer_manager.my_node_id, 'my_node_id')
        self.assertEqual(self.peer_manager.peers, {})
        self.assertEqual(self.peer_manager.pending_requests, {})


    def test_remove_peer(self):
        """测试移除peer"""
        peer_mock = Mock()
        peer_mock.node_id = 'test_node_id'
        self.peer_manager.peers['test_node_id'] = peer_mock
        
        # 执行移除
        self.loop.run_until_complete(self.peer_manager.remove_peer(peer_mock))
        
        # 验证peer已被移除
        self.assertNotIn('test_node_id', self.peer_manager.peers)
        self.event_bus_mock.publish.assert_called_once_with('peer_disconnected', peer_mock)

    @patch('src.p2p.peer.Peer')
    def test_broadcast(self, mock_peer_class):
        """测试广播消息"""
        # 创建模拟peers
        peer1 = Mock()
        peer1.send_message = AsyncMock()
        peer2 = Mock()
        peer2.send_message = AsyncMock()
        
        self.peer_manager.peers = {
            'peer1': peer1,
            'peer2': peer2
        }
        
        # 执行广播
        self.loop.run_until_complete(
            self.peer_manager.broadcast('test_msg', {'data': 'test'})
        )
        
        # 验证消息发送给所有peers
        peer1.send_message.assert_called_once_with('test_msg', {'data': 'test'})
        peer2.send_message.assert_called_once_with('test_msg', {'data': 'test'})

    @patch('src.p2p.peer.Peer')
    def test_broadcast_with_exclude(self, mock_peer_class):
        """测试带排除的广播消息"""
        # 创建模拟peers
        peer1 = Mock()
        peer1.send_message = AsyncMock()
        peer2 = Mock()
        peer2.send_message = AsyncMock()
        
        self.peer_manager.peers = {
            'peer1': peer1,
            'peer2': peer2
        }
        
        # 执行广播，排除peer1
        self.loop.run_until_complete(
            self.peer_manager.broadcast('test_msg', {'data': 'test'}, exclude_peer=peer1)
        )
        
        # 验证消息只发送给了peer2
        peer1.send_message.assert_not_called()
        peer2.send_message.assert_called_once_with('test_msg', {'data': 'test'})

    def test_resolve_request_found(self):
        """测试解析找到的请求"""
        # 设置待处理请求
        future = asyncio.Future()
        self.peer_manager.pending_requests['req_123'] = future
        
        # 解析响应
        result = self.peer_manager.resolve_request({
            'payload': {
                'request_id': 'req_123',
                'data': 'response_data'
            }
        })
        
        # 验证结果
        self.assertTrue(result)
        self.assertTrue(future.done())
        self.assertEqual(future.result(), {
            'request_id': 'req_123',
            'data': 'response_data'
        })
        self.assertNotIn('req_123', self.peer_manager.pending_requests)

    def test_resolve_request_not_found(self):
        """测试解析未找到的请求"""
        # 解析不存在的请求
        result = self.peer_manager.resolve_request({
            'payload': {
                'request_id': 'unknown_req',
                'data': 'response_data'
            }
        })
        
        # 验证结果
        self.assertFalse(result)


if __name__ == '__main__':
    unittest.main()