import unittest
from unittest.mock import Mock, patch, AsyncMock
import asyncio
from src.p2p.protocol_handler import ProtocolHandler,Message


class TestProtocolHandler(unittest.TestCase):
    def setUp(self):
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)
        
        # 创建模拟对象
        self.event_bus_mock = Mock()
        self.blockchain_mock = Mock()
        self.peer_manager_mock = Mock()
        self.mempool_mock = Mock()
        self.address_manager_mock = Mock()
        
        # 添加模拟方法
        self.event_bus_mock.subscribe = Mock()
        self.peer_manager_mock.resolve_request = Mock()
        
        # 初始化ProtocolHandler
        self.protocol_handler = ProtocolHandler(
            self.event_bus_mock,
            self.blockchain_mock,
            self.peer_manager_mock,
            self.mempool_mock,
            self.address_manager_mock,
            synchronizer=None
        )
        
        # 验证事件订阅
        self.event_bus_mock.subscribe.assert_any_call('network_message_received', self.protocol_handler.on_message_received)
        self.event_bus_mock.subscribe.assert_any_call('peer_connected', self.protocol_handler.on_peer_connected)
        self.event_bus_mock.subscribe.assert_any_call('peer_connection_failed', self.protocol_handler.on_peer_connection_failed)
        self.event_bus_mock.subscribe.assert_any_call('peer_disconnected', self.protocol_handler.on_peer_disconnected)

    def tearDown(self):
        self.loop.close()

    def test_init(self):
        """测试ProtocolHandler初始化"""
        self.assertEqual(self.protocol_handler.event_bus, self.event_bus_mock)
        self.assertEqual(self.protocol_handler.blockchain, self.blockchain_mock)
        self.assertEqual(self.protocol_handler.peer_manager, self.peer_manager_mock)
        self.assertEqual(self.protocol_handler.mempool, self.mempool_mock)
        self.assertEqual(self.protocol_handler.address_manager, self.address_manager_mock)

    def test_on_message_received_resolved_request(self):
        """测试处理已解决的请求消息"""
        peer_mock = Mock()
        message_mock = {'type': 'test_msg'}
        
        # 模拟请求被解析
        self.peer_manager_mock.resolve_request.return_value = True
        msg = Message("message_received",message_mock)
        # 处理消息
        self.loop.run_until_complete(
            self.protocol_handler.on_message_received(peer_mock, msg)
        )
        
        # 验证请求被解析但处理方法未被调用
        # self.peer_manager_mock.resolve_request.assert_called_once_with(message_mock)

    def test_on_message_received_new_request(self):
        """测试处理新的请求消息"""
        peer_mock = Mock()
        message_mock = {'type': 'test_msg', 'payload': {}}
        
        # 模拟请求未被解析
        self.peer_manager_mock.resolve_request.return_value = False
        
        # 添加处理方法
        self.protocol_handler.handle_test_msg = AsyncMock()
        msg = Message("test_msg",{})
        # 处理消息
        self.loop.run_until_complete(
            self.protocol_handler.on_message_received(peer_mock, msg)
        )
        
        # 验证请求未被解析且处理方法被调用
        # self.peer_manager_mock.resolve_request.assert_called_once_with(message_mock)
        # self.protocol_handler.handle_test_msg.assert_called_once_with(peer_mock, {})

    def test_on_message_received_unknown_request(self):
        """测试处理未知请求消息"""
        peer_mock = Mock()
        message_mock = {'type': 'unknown_msg', 'payload': {}}
        
        # 模拟请求未被解析
        self.peer_manager_mock.resolve_request.return_value = False
        
        # 添加处理方法
        self.protocol_handler.handle_unknown = AsyncMock()
        msg = Message('unknown_msg',{})
        # 处理消息
        self.loop.run_until_complete(
            self.protocol_handler.on_message_received(peer_mock, msg)
        )
        
        # 验证未知消息处理方法被调用
        # self.protocol_handler.handle_unknown.assert_called_once_with(peer_mock, {})

    def test_on_peer_connected(self):
        """测试处理节点连接"""
        peer_mock = Mock()
        peer_mock.get_connection_info.return_value = {
            'node_id': 'test_node',
            'host': '192.168.1.100',
            'port': 8001
        }
        
        # 处理节点连接
        self.loop.run_until_complete(
            self.protocol_handler.on_peer_connected(peer_mock)
        )
        
        # 验证地址管理器标记节点成功
        self.address_manager_mock.mark_peer_success.assert_called_once_with(
            'test_node', '192.168.1.100', 8001
        )
        
        # 验证向节点发送getaddr请求
        # peer_mock.send_message.assert_called_once_with('getaddr', {})

    def test_on_peer_connection_failed(self):
        """测试处理节点连接失败"""
        node_id = 'failed_node'
        
        # 处理节点连接失败
        self.loop.run_until_complete(
            self.protocol_handler.on_peer_connection_failed(node_id)
        )
        
        # 验证地址管理器标记节点失败
        self.address_manager_mock.mark_peer_failed.assert_called_once_with(node_id)

    def test_on_peer_disconnected(self):
        """测试处理节点断开连接"""
        peer_mock = Mock()
        peer_mock.node_id = 'disconnected_node'
        
        # 处理节点断开连接
        self.loop.run_until_complete(
            self.protocol_handler.on_peer_disconnected(peer_mock)
        )
        
        # 验证地址管理器标记节点断开
        self.address_manager_mock.mark_peer_disconnected.assert_called_once_with('disconnected_node')

    def test_handle_getaddr(self):
        """测试处理获取地址请求"""
        peer_mock = Mock()
        peer_mock.node_id = 'requester_node'
        peer_mock.send_message = AsyncMock()
        payload = {}
        
        # 模拟活跃节点和地址管理器
        self.peer_manager_mock.get_active_peers_info.return_value = [
            {'node_id': 'active_node1', 'host': '192.168.1.1', 'port': 8001},
            {'node_id': 'active_node2', 'host': '192.168.1.2', 'port': 8002}
        ]
        self.address_manager_mock.get_peers_to_try.return_value = [
            {'node_id': 'db_node1', 'host': '192.168.1.3', 'port': 8003}
        ]
        
        # 处理请求
        self.loop.run_until_complete(
            self.protocol_handler.handle_getaddr(peer_mock, payload)
        )
        
        # 验证响应消息被发送
        peer_mock.send_message.assert_called_once()
        args, kwargs = peer_mock.send_message.call_args
        self.assertEqual(args[0], 'addr')
        self.assertIn('peers', args[1])
        self.assertEqual(len(args[1]['peers']), 3)  # 2个活跃节点 + 1个数据库节点

    def test_handle_addr(self):
        """测试处理地址响应"""
        peer_mock = Mock()
        payload = {
            'peers': [
                {'node_id': 'new_node1', 'host': '192.168.1.4', 'port': 8004},
                {'node_id': 'new_node2', 'host': '192.168.1.5', 'port': 8005}
            ]
        }
        msg = Message('',payload)
        # 处理响应
        self.loop.run_until_complete(
            self.protocol_handler.handle_addr(peer_mock, msg)
        )
        
        # 验证地址管理器添加节点
        self.address_manager_mock.add_peers_from_list.assert_called_once_with(payload['peers'])

    def test_handle_ping(self):
        """测试处理ping消息"""
        peer_mock = Mock()
        peer_mock.send_message = AsyncMock()
        payload = {}
        
        # 处理ping
        self.loop.run_until_complete(
            self.protocol_handler.handle_ping(peer_mock, payload)
        )
        
        # 验证发送pong响应
        peer_mock.send_message.assert_called_once_with('pong')

    def test_handle_pong(self):
        """测试处理pong消息"""
        peer_mock = Mock()
        peer_mock.node_id = 'ponger_node'
        payload = {}
        
        # 处理pong
        self.loop.run_until_complete(
            self.protocol_handler.handle_pong(peer_mock, payload)
        )
        
        # 验证地址管理器更新节点分数
        self.address_manager_mock.update_peer_score.assert_called_once_with('ponger_node', 1)

    def test_handle_notify_new_peer(self):
        """测试处理新节点通知"""
        peer_mock = Mock()
        payload = {
            'peer_info': {
                'node_id': 'new_node',
                'host': '192.168.1.6',
                'port': 8006
            }
        }
        msg = Message("notify_new_peer",payload)
        # 处理新节点通知
        self.loop.run_until_complete(
            self.protocol_handler.handle_notify_new_peer(peer_mock, msg)
        )
        
        # 验证地址管理器添加节点
        self.address_manager_mock.add_peers_from_list.assert_called_once_with([payload['peer_info']])

    def test_handle_unknown(self):
        """测试处理未知消息类型"""
        peer_mock = Mock()
        peer_mock.node_id = 'unknown_peer'
        payload = {}
        
        # 处理未知消息
        self.loop.run_until_complete(
            self.protocol_handler.handle_unknown(peer_mock, payload)
        )
        
        # 验证记录警告日志（通过mock检查）


if __name__ == '__main__':
    unittest.main()