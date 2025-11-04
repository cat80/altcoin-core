import unittest
from unittest.mock import Mock, patch, AsyncMock
import asyncio
import json
import struct
from src.p2p.protocol import protocol, NETWORK_MAGIC_HEADER, HEADER_FORMAT


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

    def test_serialize_message_structure(self):
        """测试消息序列化结构"""
        payload_data = {'test': 'data'}
        result = protocol.serialize_message('test_type', payload_data)
        
        # 验证头部存在
        self.assertTrue(result.startswith(NETWORK_MAGIC_HEADER))
        
        # 解析头部
        header_size = struct.calcsize(HEADER_FORMAT)
        magic, checksum, payload_len = struct.unpack(HEADER_FORMAT, result[:header_size])
        
        # 验证头部字段
        self.assertEqual(magic, NETWORK_MAGIC_HEADER)
        self.assertEqual(checksum, b'\x00\x00\x00\x00')
        self.assertEqual(payload_len, len(result[header_size:]))
        
        # 验证载荷
        payload = json.loads(result[header_size:].decode('utf8'))
        self.assertEqual(payload['type'], 'test_type')
        self.assertEqual(payload['payload'], payload_data)

    def test_create_ping(self):
        """测试创建ping消息"""
        ping_msg = protocol.create_ping()
        self.assertIsInstance(ping_msg, bytes)
        self.assertGreater(len(ping_msg), 0)
        self.assertIn(b'ping', ping_msg)

    def test_create_pong(self):
        """测试创建pong消息"""
        pong_msg = protocol.create_pong()
        self.assertIsInstance(pong_msg, bytes)
        self.assertGreater(len(pong_msg), 0)
        self.assertIn(b'pong', pong_msg)

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