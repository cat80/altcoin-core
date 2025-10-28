import asyncio
import logging

from .protocol import protocol # 引用你的 protocol.py
from .peer_manager import PeerManager
from .event_bus import EventBus

log = logging.getLogger(__name__)
class Peer:
    def __init__(self, node_id: str, reader, writer,
                 peer_manager: PeerManager, event_bus: EventBus):
        self.node_id = node_id
        self.reader = reader
        self.writer = writer
        self.peer_manager = peer_manager
        self.event_bus = event_bus

        # 每个 Peer 都有自己独立的消息读取循环任务
        self.main_loop_task = asyncio.create_task(self._run_message_loop())

    async def _run_message_loop(self):
        """
        这是此 Peer 的主循环，只负责读消息和发事件。
        """
        addr = self.writer.get_extra_info('peername')
        buffer = b''
        try:
            while True:
                # 1. 使用你的协议反序列化消息
                message, buffer = await AsyncProtocol.deserialize_stream(self.reader, buffer)
                if message is None:
                    break # 连接断开

                # 2. **核心解耦**: Peer 不处理消息，而是发布事件
                #    ProtocolHandler 将会订阅这个事件
                await self.event_bus.publish('network_message_received', self, message)

        except asyncio.CancelledError:
            log.debug(f"Loop for {self.node_id} cancelled.")
        except Exception as e:
            log.debug(f"Message loop for {self.node_id} error: {e}")
        finally:
            # 循环结束（无论何种原因），通知 PeerManager 移除自己
            await self.peer_manager.remove_peer(self)

    async def send_message(self, msgtype: str, payload=None):
        """向这个对等节点发送消息的API"""
        try:
            # 1. 使用你的协议序列化消息
            message_bytes = protocol.serialize_message(msgtype, payload)
            self.writer.write(message_bytes)
            await self.writer.drain()
        except Exception as e:
            log.debug(f"Failed to send message to {self.node_id}: {e}")
            await self.peer_manager.remove_peer(self) # 发送失败，移除

    async def close(self):
        """关闭此连接"""
        self.main_loop_task.cancel()
        if not self.writer.is_closing():
            self.writer.close()
            await self.writer.wait_closed()
