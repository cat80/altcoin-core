import asyncio
import logging
from typing import Optional,Dict

from sqlalchemy.testing import future
from sqlalchemy.util import assert_arg_type

from .protocol import protocol,Message
import uuid
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

        # 用说监听响应模式
        self.pending_requests :Dict[str,asyncio.Future] = {}

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
                message_dict, buffer = await protocol.deserialize_stream(self.reader, buffer)
                log.debug(f'recv from-{self.get_connection_info()}\n{message_dict}')
                if message_dict is None:
                    log.info(f"Connection to {self.node_id} @ {addr} closed.")
                    break
                message = Message.from_dict(message_dict) # 转换成message对象
                log.debug(f'current pending_requests:{self.pending_requests.keys()}')
                if message.response_to and message.response_to in self.pending_requests:
                    # 这是一个响应，兑现Future
                    log.debug(f'收到响应的消息:{message_dict}')
                    future_wait = self.pending_requests.pop(message.response_to)
                    future_wait.set_result(message)
                    await asyncio.sleep(0)
                else:
                    # log.debug(f'recv from-{self.get_connection_info()}\n{message}')
                    await self.event_bus.publish('network_message_received', self, message)

        except asyncio.CancelledError:
            log.debug(f"Message loop for {self.node_id} cancelled.")
        except Exception as e:
            log.debug(f"Exception details for message loop for {self.node_id} @ {addr}:", exc_info=True)
            log.error(f"Message loop for {self.node_id} @ {addr} error: {e}")
        finally:
            await self.peer_manager.remove_peer(self)
    async def send(self,msg:Message):
        """向这个对等节点发送消息的API"""
        try:
            message_bytes = protocol.serialize(msg)
            self.writer.write(message_bytes)
            await self.writer.drain()
        except Exception as e:
            log.debug(f"Exception details for sending message to {self.node_id}:", exc_info=True)
            log.error(f"Failed to send message to {self.node_id}: {e}")
            await self.peer_manager.remove_peer(self)

    async def send_message(self, msgtype: str, payload=None,request_id:Optional[str] =None,response_to=None):
        """向这个对等节点发送消息的API"""
        msg = Message(msg_type=msgtype,payload=payload)
        msg.request_id = request_id
        msg.response_to =response_to
        await self.send(msg) #发送数据

    async def reqeust_wait_response(self,msg_type,payload=None,timeout=30)->Message:
        """
            把异步消息变成同步请求
        :param msg_type:
        :param payload:
        :param timeout:
        :return:
        """
        request_id= str(uuid.uuid4())
        wait_future = asyncio.get_running_loop().create_future()
        self.pending_requests[request_id] = wait_future
        log.debug(f'开发送消息:{msg_type},{payload},{request_id}')
        await self.send_message(msg_type,payload, request_id = request_id) # wait
        log.debug(f'发送消息完成:{msg_type},{payload},{request_id}')
        try:
            log.debug(f'开始等待返回:{msg_type},{payload},{request_id}')
            response_message  = await asyncio.wait_for(wait_future,timeout=timeout)
            log.debug(f'数据返回成功:{msg_type},{payload},{request_id}')
            return response_message
        except asyncio.TimeoutError:
            if request_id in self.pending_requests:
                log.warning(f'futrue等等超时，删除:{request_id},当前futrue数:{len(self.pending_requests.keys())}')
                del self.pending_requests[request_id]
            log.warning(f'request [{msg_type}] to {self.get_connection_info()} time out')
            raise
    async def close(self):
        """关闭此连接"""
        if not self.main_loop_task.done():
            self.main_loop_task.cancel()

        for future_time in self.pending_requests.values():
            future_time.cancel()
        self.pending_requests.clear()
        if not self.writer.is_closing():
            try:
                self.writer.close()
                await self.writer.wait_closed()
            except Exception as e:
                log.debug(f"Exception details while closing writer for {self.node_id}:", exc_info=True)
                log.warning(f"Error while closing writer for {self.node_id}: {e}")
        await self.event_bus.publish('peer_disconnected', self)