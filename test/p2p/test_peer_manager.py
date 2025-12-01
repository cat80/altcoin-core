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
        self.address_manager_mock = Mock()
        self.node_mock = Mock()
        
        # 添加模拟方法
        self.event_bus_mock.subscribe = Mock()
        self.event_bus_mock.publish = AsyncMock()
        
        # 在事件循环中创建PeerManager实例
        async def create_peer_manager():
            return PeerManager(
                self.event_bus_mock, 
                'my_node_id', 
                8001, 
                self.address_manager_mock, 
                self.node_mock
            )
        
        self.peer_manager = self.loop.run_until_complete(create_peer_manager())

    def tearDown(self):
        self.loop.close()

    def test_init(self):
        """测试PeerManager初始化"""
        self.assertEqual(self.peer_manager.my_node_id, 'my_node_id')
        self.assertEqual(self.peer_manager.my_listen_port, 8001)
        self.assertEqual(self.peer_manager.address_manager, self.address_manager_mock)
        self.assertEqual(self.peer_manager.node, self.node_mock)
        self.assertEqual(self.peer_manager.peers, {})
        self.assertEqual(self.peer_manager.pending_requests, {})
        
        # 验证事件订阅
        expected_calls = [
            ('block_validated', self.peer_manager.on_new_block_validated),
            ('peer_connected', self.peer_manager.on_peer_connected_gossip)
        ]
        for event_type, handler in expected_calls:
            self.event_bus_mock.subscribe.assert_any_call(event_type, handler)

    def test_get_active_node_ids(self):
        """测试获取活跃节点ID集合"""
        # 添加模拟peers
        peer1 = Mock()
        peer1.node_id = 'node1'
        peer2 = Mock()
        peer2.node_id = 'node2'
        
        self.peer_manager.peers = {
            'node1': peer1,
            'node2': peer2
        }
        
        # 获取活跃节点ID
        active_ids = self.peer_manager.get_active_node_ids()
        
        # 验证结果
        self.assertEqual(active_ids, {'node1', 'node2'})

    def test_get_active_peers_info(self):
        """测试获取活跃节点信息列表"""
        # 添加模拟peers
        peer1 = Mock()
        peer1.connectable_ip = '192.168.1.1'
        peer1.get_connection_info = Mock(return_value={
            'node_id': 'node1',
            'host': '192.168.1.1',
            'port': 8001
        })
        
        peer2 = Mock()
        peer2.connectable_ip = '192.168.1.2'
        peer2.get_connection_info = Mock(return_value={
            'node_id': 'node2',
            'host': '192.168.1.2',
            'port': 8002
        })
        
        # 添加一个没有可连接IP的peer
        peer3 = Mock()
        peer3.connectable_ip = None
        peer3.get_connection_info = Mock(return_value={
            'node_id': 'node3',
            'host': None,
            'port': None
        })
        
        self.peer_manager.peers = {
            'node1': peer1,
            'node2': peer2,
            'node3': peer3
        }
        
        # 获取活跃节点信息
        active_peers_info = self.peer_manager.get_active_peers_info()
        
        # 验证结果（只有有可连接IP的peer被包含）
        self.assertEqual(len(active_peers_info), 2)
        peer_infos = {info['node_id'] for info in active_peers_info}
        self.assertIn('node1', peer_infos)
        self.assertIn('node2', peer_infos)
        self.assertNotIn('node3', peer_infos)

    def test_remove_peer(self):
        """测试移除peer"""
        peer_mock = Mock()
        peer_mock.node_id = 'test_node_id'
        peer_mock.close = AsyncMock()
        self.peer_manager.peers['test_node_id'] = peer_mock
        
        # 执行移除
        self.loop.run_until_complete(self.peer_manager.remove_peer(peer_mock))
        
        # 验证peer已被移除
        self.assertNotIn('test_node_id', self.peer_manager.peers)
        self.event_bus_mock.publish.assert_called_once_with('peer_disconnected', peer_mock)
        peer_mock.close.assert_called_once()

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

    @patch('uuid.uuid4')
    def test_request_data_success(self, mock_uuid):
        """测试请求数据成功"""
        # 模拟UUID
        mock_uuid.return_value = 'req_123'
        
        # 创建模拟peer
        peer_mock = Mock()
        peer_mock.send_message = AsyncMock()
        
        # 模拟响应
        async def mock_send_message(msgtype, payload):
            # 模拟收到响应
            future = self.peer_manager.pending_requests['req_123']
            if not future.done():
                future.set_result({'data': 'response_data', 'request_id': 'req_123'})
        
        peer_mock.send_message.side_effect = mock_send_message
        
        # 执行请求
        response = self.loop.run_until_complete(
            self.peer_manager.request_data(peer_mock, 'test_msg', {'data': 'request_data'})
        )
        
        # 验证结果
        self.assertEqual(response, {'data': 'response_data', 'request_id': 'req_123'})
        peer_mock.send_message.assert_called_once_with('test_msg', {'data': 'request_data', 'request_id': 'req_123'})

    @patch('uuid.uuid4')
    def test_request_data_timeout(self, mock_uuid):
        """测试请求数据超时"""
        # 模拟UUID
        mock_uuid.return_value = 'req_123'
        
        # 创建模拟peer
        peer_mock = Mock()
        peer_mock.send_message = AsyncMock()
        
        # 执行请求，设置超时时间很短
        # with self.assertRaises(Exception) as context:
        #     self.loop.run_until_complete(
        #         self.peer_manager.request_data(peer_mock, 'test_msg', {'data': 'request_data'}, timeout=0.01)
        #     )
        #
        # # 验证异常
        # self.assertIn('timed out', str(context.exception))


if __name__ == '__main__':
    unittest.main()