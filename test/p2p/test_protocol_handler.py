import unittest
from unittest.mock import Mock, patch, AsyncMock
import asyncio
from src.p2p.protocol_handler import ProtocolHandler


class TestProtocolHandler(unittest.TestCase):
    def setUp(self):
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)
        
        # 创建模拟对象
        self.event_bus_mock = Mock()
        self.blockchain_mock = Mock()
        self.peer_manager_mock = Mock()
        self.mempool_mock = Mock()
        
        # 初始化ProtocolHandler
        self.protocol_handler = ProtocolHandler(
            self.event_bus_mock,
            self.blockchain_mock,
            self.peer_manager_mock,
            self.mempool_mock
        )
        
        # 添加模拟方法
        self.event_bus_mock.subscribe = Mock()
        self.peer_manager_mock.resolve_request = Mock()

    def tearDown(self):
        self.loop.close()

    def test_init(self):
        """测试ProtocolHandler初始化"""
        self.assertEqual(self.protocol_handler.event_bus, self.event_bus_mock)
        self.assertEqual(self.protocol_handler.blockchain, self.blockchain_mock)
        self.assertEqual(self.protocol_handler.peer_manager, self.peer_manager_mock)
        self.assertEqual(self.protocol_handler.mempool, self.mempool_mock)

    def test_on_message_received_resolved_request(self):
        """测试处理已解决的请求消息"""
        peer_mock = Mock()
        message_mock = {'type': 'test_msg'}
        
        # 模拟请求被解析
        self.peer_manager_mock.resolve_request.return_value = True
        
        # 处理消息
        self.loop.run_until_complete(
            self.protocol_handler.on_message_received(peer_mock, message_mock)
        )
        
        # 验证请求被解析但处理方法未被调用
        self.peer_manager_mock.resolve_request.assert_called_once_with(message_mock)
        self.assertFalse(hasattr(self.protocol_handler, 'handle_test_msg'))

    def test_on_message_received_new_request(self):
        """测试处理新的请求消息"""
        peer_mock = Mock()
        message_mock = {'type': 'test_msg', 'payload': {}}
        
        # 模拟请求未被解析
        self.peer_manager_mock.resolve_request.return_value = False
        
        # 添加处理方法
        self.protocol_handler.handle_test_msg = AsyncMock()
        
        # 处理消息
        self.loop.run_until_complete(
            self.protocol_handler.on_message_received(peer_mock, message_mock)
        )
        
        # 验证请求未被解析且处理方法被调用
        self.peer_manager_mock.resolve_request.assert_called_once_with(message_mock)
        self.protocol_handler.handle_test_msg.assert_called_once_with(peer_mock, {})

    def test_on_message_received_unknown_request(self):
        """测试处理未知请求消息"""
        peer_mock = Mock()
        message_mock = {'type': 'unknown_msg', 'payload': {}}

    def test_handle_get_best_tip(self):
        """测试处理获取最佳提示请求"""
        peer_mock = Mock()
        peer_mock.send_message = AsyncMock()
        payload = {'request_id': 'req_123'}
        
        # 模拟区块链获取最佳提示
        self.blockchain_mock.get_best_tip.return_value = {'height': 100, 'hash': 'abcd1234'}
        
        # 处理请求
        self.loop.run_until_complete(
            self.protocol_handler.handle_get_best_tip(peer_mock, payload)
        )
        
        # 验证响应消息被发送
        peer_mock.send_message.assert_called_once_with(
            'best_tip_response',
            {'tip_info': {'height': 100, 'hash': 'abcd1234'}, 'request_id': 'req_123'}
        )

    @patch('src.core.block.Block')
    def test_handle_get_block_info_found(self, mock_block_class):
        """测试处理获取区块信息请求（找到区块）"""
        peer_mock = Mock()
        peer_mock.send_message = AsyncMock()
        payload = {'hash_hex': 'abcd1234', 'request_id': 'req_123'}
        
        # 模拟找到区块
        mock_block_instance = Mock()
        mock_block_instance.serialize.return_value = b'serialized_block_data'
        self.blockchain_mock.block_storage.read_block_by_hash.return_value = mock_block_instance
        
        # 处理请求
        self.loop.run_until_complete(
            self.protocol_handler.handle_get_block_info(peer_mock, payload)
        )
        
        # 验证响应消息被发送
        peer_mock.send_message.assert_called_once_with(
            'block_info_response',
            {'block_data': b'serialized_block_data', 'request_id': 'req_123'}
        )

    def test_handle_get_block_info_not_found(self):
        """测试处理获取区块信息请求（未找到区块）"""
        peer_mock = Mock()
        peer_mock.send_message = AsyncMock()
        payload = {'hash_hex': 'abcd1234', 'request_id': 'req_123'}
        
        # 模拟未找到区块
        self.blockchain_mock.block_storage.read_block_by_hash.return_value = None
        
        # 处理请求
        self.loop.run_until_complete(
            self.protocol_handler.handle_get_block_info(peer_mock, payload)
        )
        
        # 验证响应消息被发送（无区块数据）
        peer_mock.send_message.assert_called_once_with(
            'block_info_response',
            {'block_data': None, 'request_id': 'req_123'}
        )

    @patch('src.core.block.Block')
    def test_handle_notify_new_block_header_known(self, mock_block_class):
        """测试处理新区块头通知（已知区块）"""
        peer_mock = Mock()
        payload = {'header': 'header_data'}
        
        # 模拟已知区块头
        self.blockchain_mock.block_index.get_header_info.return_value = {'exists': True}
        




if __name__ == '__main__':
    unittest.main()