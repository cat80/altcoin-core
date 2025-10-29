import asyncio
import uuid
import logging
from typing import Dict, Optional

from .event_bus import EventBus
from .peer import Peer
from .protocol import protocol

log = logging.getLogger(__name__)

class PeerManager:
    def __init__(self, event_bus: EventBus, my_node_id: str, my_listen_port: int):
        self.event_bus = event_bus
        self.my_node_id = my_node_id
        self.my_listen_port = my_listen_port
        self.peers: Dict[str, Peer] = {}
        self.pending_requests: Dict[str, asyncio.Future] = {}

        self.event_bus.subscribe('block_validated', self.on_new_block_validated)
        # 订阅 peer_connected 事件，以实现 PUSH 广播
        self.event_bus.subscribe('peer_connected', self.on_peer_connected_gossip)

    async def on_peer_connected_gossip(self, new_peer: Peer):
        """
        [EventBus 调用] 这是“统一逻辑”的 PUSH 部分：广播新节点。
        """
        peer_info = new_peer.get_connection_info()
        if not peer_info or not peer_info['ip']:
            log.warning(f"无法广播新节点 {new_peer.node_id}，缺少连接信息")
            return

        log.debug(f"Gossip: 广播新节点 {peer_info['node_id']} 给其他邻居")
        await self.broadcast(
            'notify_new_peer',
            {'peer_info': peer_info},
            exclude_peer=new_peer
        )

    async def start_handshake(self, reader, writer, is_initiator: bool):
        """处理握手和重复连接"""
        remote_node_id = None
        try:
            # 1. 握手：发送我们自己的 listen_port
            hello_msg_payload = {
                'type': 'hello',
                'node_id': self.my_node_id,
                'listen_port': self.my_listen_port
            }
            writer.write(protocol.serialize_message('hello', hello_msg_payload))
            await writer.drain()

            remote_hello_msg, _ = await protocol.deserialize_stream(reader, b'')

            if not remote_hello_msg or remote_hello_msg.get('type') != 'hello':
                raise Exception("Handshake failed: Invalid 'hello' response")

            # 获取对方的 ID 和 Port
            payload = remote_hello_msg['payload']
            remote_node_id = payload.get('node_id')
            remote_listen_port = payload.get('listen_port')
            remote_ip = writer.get_extra_info('peername')[0]

            if not remote_node_id or not remote_listen_port or remote_node_id == self.my_node_id:
                raise Exception(f"Invalid remote peer data: {remote_node_id} @ {remote_ip}:{remote_listen_port}")

            # 2. 重复连接处理
            if remote_node_id in self.peers:
                if is_initiator and self.my_node_id > remote_node_id:
                    raise Exception(f"Dropping duplicate (initiator) connection to {remote_node_id}")
                elif not is_initiator and self.my_node_id < remote_node_id:
                    raise Exception(f"Dropping duplicate (receiver) connection to {remote_node_id}")
                else:
                    log.info(f"Replacing duplicate connection for {remote_node_id}")
                    await self.peers[remote_node_id].close()

            # 3. 握手成功：创建 Peer 并设置其可连接地址
            log.info(f"Handshake successful with {remote_node_id} @ {remote_ip}:{remote_listen_port}")
            peer = Peer(remote_node_id, reader, writer, self, self.event_bus)
            peer.set_connectable_address(remote_ip, remote_listen_port)
            self.peers[remote_node_id] = peer
            await self.event_bus.publish('peer_connected', peer)

        except Exception as e:
            log.error(f"Handshake failed: {e}")
            if remote_node_id:
                await self.event_bus.publish('peer_connection_failed', remote_node_id)
            if not writer.is_closing():
                writer.close()
                await writer.wait_closed()

    async def remove_peer(self, peer: Peer):
        popped_peer = self.peers.pop(peer.node_id, None)
        if popped_peer:
            log.info(f"Peer disconnected: {peer.node_id}")
            await self.event_bus.publish('peer_disconnected', peer)
            await peer.close()

    async def broadcast(self, msgtype: str, payload: dict, exclude_peer: Optional[Peer] = None):
        """向所有节点广播"""
        tasks = [
            peer.send_message(msgtype, payload)
            for peer in self.peers.values() if peer != exclude_peer
        ]
        await asyncio.gather(*tasks)

    async def request_data(self, peer: Peer, msgtype: str, payload: dict, timeout=10.0) -> dict:
        """业务逻辑调用此方法，以“同步”的方式等待响应"""
        request_id = str(uuid.uuid4())
        future = asyncio.Future()
        self.pending_requests[request_id] = future
        payload['request_id'] = request_id

        try:
            await peer.send_message(msgtype, payload)
            response_payload = await asyncio.wait_for(future, timeout)
            return response_payload
        except asyncio.TimeoutError:
            raise Exception(f"Request {request_id} ({msgtype}) timed out")
        finally:
            self.pending_requests.pop(request_id, None)

    def resolve_request(self, response_message: dict) -> bool:
        """由 ProtocolHandler 调用，检查消息是否是响应"""
        request_id = response_message.get('payload', {}).get('request_id')
        if request_id and request_id in self.pending_requests:
            future = self.pending_requests.pop(request_id, None)
            if future and not future.done():
                future.set_result(response_message['payload'])
            return True
        return False

    async def on_new_block_validated(self, block):
        """事件订阅示例：自动广播新区块头"""
        # header_data = block.header.serialize()
        # await self.broadcast('notify_new_block_header', {'header': header_data})
        pass # 暂时禁用