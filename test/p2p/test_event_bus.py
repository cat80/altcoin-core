import unittest
from unittest.mock import Mock, patch, AsyncMock
import asyncio
from src.p2p.event_bus import EventBus


class TestEventBus(unittest.TestCase):
    def setUp(self):
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)
        self.event_bus = EventBus()

    def tearDown(self):
        self.loop.close()

    def test_subscribe_and_publish(self):
        """测试事件订阅和发布功能"""
        callback_mock = AsyncMock()
        self.event_bus.subscribe('test_event', callback_mock)
        
        # 发布事件
        self.loop.run_until_complete(
            self.event_bus.publish('test_event', 'arg1', kwarg1='value1')
        )
        
        # 验证回调函数被调用
        callback_mock.assert_called_once_with('arg1', kwarg1='value1')

    def test_publish_no_subscribers(self):
        """测试发布没有订阅者的事件"""
        # 不订阅任何事件，直接发布
        result = self.loop.run_until_complete(
            self.event_bus.publish('nonexistent_event')
        )
        
        # 应该正常执行，无异常
        self.assertIsNone(result)

    def test_multiple_subscribers(self):
        """测试多个订阅者"""
        callback1 = AsyncMock()
        callback2 = AsyncMock()
        
        self.event_bus.subscribe('multi_event', callback1)
        self.event_bus.subscribe('multi_event', callback2)
        
        self.loop.run_until_complete(
            self.event_bus.publish('multi_event', 'data')
        )
        
        # 验证两个回调都被调用
        callback1.assert_called_once_with('data')
        callback2.assert_called_once_with('data')
        
    def test_publish_with_exception_in_callback(self):
        """测试当回调函数抛出异常时的处理"""
        callback1 = AsyncMock(side_effect=Exception("Callback error"))
        callback2 = AsyncMock()
        
        self.event_bus.subscribe('error_event', callback1)
        self.event_bus.subscribe('error_event', callback2)
        
        # 即使有回调抛出异常，其他回调也应该被执行
        self.loop.run_until_complete(
            self.event_bus.publish('error_event', 'data')
        )
        
        callback1.assert_called_once_with('data')
        callback2.assert_called_once_with('data')


if __name__ == '__main__':
    unittest.main()