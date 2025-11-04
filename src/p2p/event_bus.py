import asyncio
from collections import defaultdict

class EventBus:
    def __init__(self):
        # 存储订阅者：{'event_name': [callback1, callback2]}
        self.subscribers = defaultdict(list)

    def subscribe(self, event_type: str, callback):
        """订阅一个事件。callback 必须是 async def"""
        self.subscribers[event_type].append(callback)

    async def publish(self, event_type: str, *args, **kwargs):
        """异步发布一个事件，并等待所有订阅者处理完毕"""
        if event_type not in self.subscribers:
            return

        # 创建所有订阅者任务
        tasks = [
            callback(*args, **kwargs)
            for callback in self.subscribers[event_type]
        ]

        # 并发执行并等待它们完成，即使有异常也继续执行其他任务
        await asyncio.gather(*tasks, return_exceptions=True)
