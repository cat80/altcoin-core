import asyncio
import logging
import typing
import uuid
from typing import Dict, Optional
from .event_bus import EventBus
from .protocol import protocol #

# init log
log = logging.getLogger(__name__)

if typing.TYPE_CHECKING:
    from .peer import Peer
class PeerManager:
    def __init__(self, event_bus: EventBus, my_node_id: str):
        from .peer import Peer
        self.event_bus = event_bus
        self.my_node_id = my_node_id
        self.peers: Dict[str, "Peer"] = {}
        # 存储 'request_id' -> asyncio.Future
        self.pending_requests: Dict[str, asyncio.Future] = {}

        # PeerManager 也可以订阅事件，例如自动广播
        self.event_bus.subscribe('block_validated', self.on_new_block_validated)

    async def start_handshake(self, reader, writer, is_initiator: bool):
        """处理握手和重复连接"""
        remote_node_id = None
        try:
            # 1. 握手：交换节点ID
            hello_msg_payload = {'type': 'hello', 'node_id': self.my_node_id}
            # (注意：这里的 'hello' 消息也需要用你的 protocol.py 来发送)
            writer.write(protocol.serialize_message('hello', hello_msg_payload))
            await writer.drain()

            # (在主循环开始前，我们进行一次阻塞式读取)
            remote_hello_msg, _ = await protocol.deserialize_stream(reader, b'')

            if not remote_hello_msg or remote_hello_msg.get('type') != 'hello':
                raise Exception("Handshake failed: Invalid 'hello' response")

            remote_node_id = remote_hello_msg['payload']['node_id']
            if not remote_node_id or remote_node_id == self.my_node_id:
                raise Exception(f"Invalid remote node ID: {remote_node_id}")

            # 2. 重复连接处理 (你提出的 tie-breaking 逻辑)
            if remote_node_id in self.peers:
                # 规则：ID 大的节点负责 *接受* 连接。
                # 如果我是发起方(is_initiator) 且 我的ID > 对方ID，我断开。
                if is_initiator and self.my_node_id > remote_node_id:
                    raise Exception(f"Dropping duplicate (initiator) connection to {remote_node_id}")
                # 如果我是被动方(not is_initiator) 且 我的ID < 对方ID，我断开。
                elif not is_initiator and self.my_node_id < remote_node_id:
                    raise Exception(f"Dropping duplicate (receiver) connection to {remote_node_id}")
                else:
                    # 否则，我们断开 *旧* 的连接，保留 *新* 的
                    log.debug(f"Replacing duplicate connection for {remote_node_id}")
                    await self.peers[remote_node_id].close()

            # 3. 握手成功：创建并注册 Peer
            log.debug(f"Handshake successful with {remote_node_id}")

            peer = Peer(remote_node_id, reader, writer, self, self.event_bus)
            self.peers[remote_node_id] = peer
            await self.event_bus.publish('peer_connected', peer)

        except Exception as e:
            log.debug(f"Handshake failed: {e}")
            if not writer.is_closing():
                writer.close()
                await writer.wait_closed()

    async def remove_peer(self, peer: "Peer"):
        popped_peer = self.peers.pop(peer.node_id, None)
        if popped_peer:
            log.debug(f"Peer disconnected: {peer.node_id}")
            await self.event_bus.publish('peer_disconnected', peer)

    async def broadcast(self, msgtype: str, payload: dict, exclude_peer: Optional["Peer"] = None):
        """向所有节点广播"""
        tasks = [
            peer.send_message(msgtype, payload)
            for peer in self.peers.values() if peer != exclude_peer
        ]
        await asyncio.gather(*tasks)

    # --- 关键的请求-响应功能 ---

    async def request_data(self, peer: "Peer", msgtype: str, payload: dict, timeout=10.0) -> dict:
        """业务逻辑调用此方法，以“同步”的方式等待响应"""
        request_id = str(uuid.uuid4())
        future = asyncio.Future()
        self.pending_requests[request_id] = future

        payload['request_id'] = request_id

        try:
            await peer.send_message(msgtype, payload)
            # 业务逻辑在这里暂停 (await)，等待 Future 完成
            response_payload = await asyncio.wait_for(future, timeout)
            return response_payload
        except asyncio.TimeoutError:
            raise Exception(f"Request {request_id} ({msgtype}) timed out")
        finally:
            self.pending_requests.pop(request_id, None)

    def resolve_request(self, response_message: dict) -> bool:
        """
        由 ProtocolHandler 调用，检查消息是否是响应
        """
        request_id = response_message.get('payload', {}).get('request_id')
        if request_id and request_id in self.pending_requests:
            future = self.pending_requests.pop(request_id)
            # 唤醒在 request_data 中等待的那个 await
            future.set_result(response_message['payload'])
            return True # 消息已处理
        return False # 这不是一个响应

    async def on_new_block_validated(self, block):
        """事件订阅示例：自动广播新区块头"""
        header_data = block.header.serialize() # (假设 header 有 .serialize())
        await self.broadcast('notify_new_block_header', {'header': header_data})
