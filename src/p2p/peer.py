import asyncio
import logging
from typing import Optional
from .protocol import protocol

# 提前导入类型，以支持类型提示
if False:
    from .peer_manager import PeerManager
    from .event_bus import EventBus


log = logging.getLogger(__name__)

class Peer:
    def __init__(self, node_id: str, reader, writer,
                 peer_manager: 'PeerManager', event_bus: 'EventBus'):
        self.node_id = node_id
        self.reader = reader
        self.writer = writer
        self.peer_manager = peer_manager
        self.event_bus = event_bus

        # 用于存储对方的“监听地址”
        self.connectable_ip: Optional[str] = None
        self.connectable_port: Optional[int] = None

        # 每个 Peer 都有自己独立的消息读取循环任务
        self.main_loop_task = asyncio.create_task(self._run_message_loop())

    def set_connectable_address(self, ip: str, port: int):
        """由 PeerManager 在握手成功后调用"""
        self.connectable_ip = ip
        self.connectable_port = port
        log.debug(f"Peer {self.node_id} connectable address set to {ip}:{port}")

    def get_connection_info(self) -> dict:
        """用于广播和存入 AddrMan"""
        return {
            "node_id": self.node_id,
            "host": self.connectable_ip,
            "port": self.connectable_port
        }

    async def _run_message_loop(self):
        """
        这是此 Peer 的主循环，只负责读消息和发事件。
        """
        addr = self.writer.get_extra_info('peername')
        buffer = b''
        try:
            while True:
                message, buffer = await protocol.deserialize_stream(self.reader, buffer)
                if message is None:
                    log.info(f"Connection to {self.node_id} @ {addr} closed.")
                    break
                # log.debug(f'recv from-{self.get_connection_info()}\n{message}')
                await self.event_bus.publish('network_message_received', self, message)

        except asyncio.CancelledError:
            log.debug(f"Message loop for {self.node_id} cancelled.")
        except Exception as e:
            log.debug(f"Exception details for message loop for {self.node_id} @ {addr}:", exc_info=True)
            log.error(f"Message loop for {self.node_id} @ {addr} error: {e}")
        finally:
            await self.peer_manager.remove_peer(self)

    async def send_message(self, msgtype: str, payload=None):
        """向这个对等节点发送消息的API"""
        try:
            message_bytes = protocol.serialize_message(msgtype, payload)
            self.writer.write(message_bytes)
            await self.writer.drain()
        except Exception as e:
            log.debug(f"Exception details for sending message to {self.node_id}:", exc_info=True)
            log.error(f"Failed to send message to {self.node_id}: {e}")
            await self.peer_manager.remove_peer(self)

    async def close(self):
        """关闭此连接"""
        if not self.main_loop_task.done():
            self.main_loop_task.cancel()
        if not self.writer.is_closing():
            try:
                self.writer.close()
                await self.writer.wait_closed()
            except Exception as e:
                log.debug(f"Exception details while closing writer for {self.node_id}:", exc_info=True)
                log.warning(f"Error while closing writer for {self.node_id}: {e}")