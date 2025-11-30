import asyncio
import uuid
import logging
from typing import Dict, Optional

from .event_bus import EventBus
from .peer import Peer
from .protocol import protocol
from .network_tools import dict_bytes_to_hex
from core.transaction import Transaction
log = logging.getLogger(__name__)

class PeerManager:
    def __init__(self, event_bus: EventBus, my_node_id: str, my_listen_port: int,
                 address_manager: 'AddressManager', node: 'Node'):
        self.event_bus = event_bus
        self.my_node_id = my_node_id
        self.my_listen_port = my_listen_port
        self.address_manager = address_manager
        self.node = node  # Node 实例，用于发起连接
        self.peers: Dict[str, Peer] = {}
        self.pending_requests: Dict[str, asyncio.Future] = {}

        self.event_bus.subscribe('block_validated', self.on_new_block_validated)
        self.event_bus.subscribe('peer_connected', self.on_peer_connected_gossip)
        self.event_bus.subscribe('new_tx_validated',self.on_new_tx_validated)
        # 启动后台维护任务
        self.maintenance_task = asyncio.create_task(self._maintenance_loop())

    async def on_new_tx_validated(self,tx:Transaction):
        # 广播新交易这里简单处理，直接广播所有的交易内容，而不是交易hash
        if not tx or not tx.verify_signature():
            return
        log.debug(f'开始广播新交易:{tx.hash().hex()}')
        # 广播新交易,这里如果新交易来自某个节点,应该当忽略，减少网络风暴，但现在不考虑。

        await self.broadcast('notify_new_tx',{'tx':tx.serialize().hex()})
    def get_active_node_ids(self) -> set:
        """返回当前所有已连接节点的 node_id 集合"""
        return set(self.peers.keys())

    def get_active_peers_info(self) -> list[dict]:
        """返回当前所有已连接节点的信息列表"""
        return [p.get_connection_info() for p in self.peers.values() if p.connectable_ip]

    async def on_peer_connected_gossip(self, new_peer: Peer):
        """
        [EventBus 调用] 这是“统一逻辑”的 PUSH 部分：广播新节点。
        """
        peer_info = new_peer.get_connection_info()
        if not peer_info or not peer_info['host']:
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
            if is_initiator:
                writer.write(protocol.serialize_message('hello', hello_msg_payload))
                await writer.drain()
                remote_hello_msg, _ = await protocol.deserialize_stream(reader, b'')
            else:
                remote_hello_msg, _ = await protocol.deserialize_stream(reader, b'')
                writer.write(protocol.serialize_message('hello', hello_msg_payload))
                await writer.drain()
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
            log.debug("Exception details for start_handshake:", exc_info=True)
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
            await self.pending_requests.pop(request_id, None)

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
        # 现在把完整的区块广播出去，应该只广播头
        try:
            log.debug(f'开始广播新区块,区块高度:{block["height"]}')
            await self.broadcast("notify_new_block_header",{
                "header":    dict_bytes_to_hex(block)
            })
        except Exception as e:
            log.debug('广播新区块出错,',exc_info=True)
    async def _maintenance_loop(self):
        """
        后台任务，定期维护节点连接数和数据库。
        """
        # 首次进来延迟5秒
        await asyncio.sleep(5)
        while True:
            try:
                # 1. 维护连接数
                active_peers_count = len(self.peers)
                if active_peers_count < 50: # 目标连接数
                    num_to_connect = 50 - active_peers_count
                    log.info(f"连接数 ({active_peers_count}) 低于目标值，尝试连接 {num_to_connect} 个新节点")
                    # 排除自身
                    active_ids = self.get_active_node_ids()
                    active_ids.add(self.my_node_id)
                    peers_to_try = self.address_manager.get_peers_to_try(
                        limit=num_to_connect,
                        exclude_ids=active_ids
                    )
                    for peer_info in peers_to_try:
                        asyncio.create_task(
                            self.node.initiate_outgoing_connection(peer_info['host'], peer_info['port'],peer_info['node_id'])
                        )

                # 2. 清理数据库
                self.address_manager.cull_bad_peers()

                # 3. 如果连接节点不够，主动去请求其它在线节点的数据，从自己的连接节点获取他们最新的节点列表。这里需要优化，比如可控制节点的访问时间，一个节点一小时只主动获取一次。
            except Exception as e:
                log.debug("Exception details for _maintenance_loop:", exc_info=True)
                log.error(f"节点维护任务出错: {e}")

            await asyncio.sleep(60*5)  # 每五分钟检查一次