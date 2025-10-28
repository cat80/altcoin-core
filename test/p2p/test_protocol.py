import unittest
from unittest.mock import Mock, patch, AsyncMock
import asyncio
from src.p2p.protocol import protocol


class TestProtocol(unittest.TestCase):
    def setUp(self):
        self.protocol = protocol()

    def test_serialize_message(self):
        """测试消息序列化"""
        # 序列化消息
        result = protocol.serialize_message('test_type', {'data': 'test'})
        
        # 验证结果类型
        self.assertIsInstance(result, bytes)
        self.assertGreater(len(result), 0)
        
        # 验证包含必要字段
        self.assertIn(b'test_type', result)
        self.assertIn(b'test', result)

    def test_serialize_message_without_payload(self):
        """测试无负载消息序列化"""
        # 序列化无负载消息
        result = protocol.serialize_message('empty_msg')
        
        # 验证结果类型
        self.assertIsInstance(result, bytes)
        self.assertGreater(len(result), 0)
        self.assertIn(b'empty_msg', result)


    def test_create_ping(self):
        """测试创建ping消息"""
        ping_msg = protocol.create_ping()
        self.assertIsInstance(ping_msg, bytes)
        self.assertGreater(len(ping_msg), 0)

    def test_create_pong(self):
        """测试创建pong消息"""
        pong_msg = protocol.create_pong()
        self.assertIsInstance(pong_msg, bytes)
        self.assertGreater(len(pong_msg), 0)

    def test_create_payload(self):
        """测试创建自定义载荷消息"""
        payload_msg = protocol.create_payload('custom_msg', {'custom': 'data'})
        self.assertIsInstance(payload_msg, bytes)
        self.assertGreater(len(payload_msg), 0)
        self.assertIn(b'custom_msg', payload_msg)
        self.assertIn(b'custom', payload_msg)
        self.assertIn(b'data', payload_msg)


if __name__ == '__main__':
    unittest.main()