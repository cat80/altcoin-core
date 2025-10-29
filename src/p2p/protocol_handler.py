import logging

from .event_bus import EventBus
from .peer_manager import PeerManager
from .peer import Peer
from core.blockchain import Blockchain
from mempool.mempool import Mempool
from .address_manager import AddressManager

log = logging.getLogger(__name__)

class ProtocolHandler:
    def __init__(self, event_bus: EventBus, blockchain: Blockchain,
                 peer_manager: PeerManager, mempool: Mempool,
                 address_manager: AddressManager):
        self.event_bus = event_bus
        self.blockchain = blockchain
        self.peer_manager = peer_manager
        self.mempool = mempool
        self.address_manager = address_manager

        # 订阅 Peer 发来的所有消息
        self.event_bus.subscribe('network_message_received', self.on_message_received)
        # ProtocolHandler 也订阅 peer_connected 以触发 PULL
        self.event_bus.subscribe('peer_connected', self.on_peer_connected)
        # 订阅连接失败事件
        self.event_bus.subscribe('peer_connection_failed', self.on_peer_connection_failed)

    async def on_peer_connected(self, peer: Peer):
        """
        [EventBus 调用] 这是“统一逻辑”的 PULL 部分：
        1. 标记节点成功 (DB)
        2. 主动拉取地址 (PULL)
        """
        # 1. 标记成功 (DB)
        conn_info = peer.get_connection_info()
        if conn_info and conn_info['ip']:
            self.address_manager.mark_peer_success(
                conn_info['node_id'], conn_info['ip'], conn_info['port']
            )

        # 2. 主动拉取地址 (PULL)
        log.debug(f"向新节点 {peer.node_id} 发送 'getaddr' 请求")
        await peer.send_message('getaddr', {})

    async def on_peer_connection_failed(self, node_id: str):
        """[EventBus 调用] 当连接失败时标记节点"""
        log.debug(f"标记节点 {node_id} 连接失败")
        self.address_manager.mark_peer_failed(node_id)

    async def on_message_received(self, peer: Peer, message: dict):
        """主消息调度器"""
        if self.peer_manager.resolve_request(message):
            return

        msg_type = message.get('type')
        payload = message.get('payload', {})

        handler_method = getattr(self, f"handle_{msg_type}", self.handle_unknown)
        await handler_method(peer, payload)

    # --- P2P 地址管理处理器 ---

    async def handle_getaddr(self, peer: Peer, payload: dict):
        """处理 'getaddr' 请求：回复我们的地址列表"""
        log.debug(f"收到 {peer.node_id} 的 'getaddr' 请求")
        peers_list = self.address_manager.get_peers_to_try(
            limit=50,
            exclude_ids={peer.node_id}
        )
        await peer.send_message('addr', {'peers': peers_list})

    async def handle_addr(self, peer: Peer, payload: dict):
        """处理 'addr' 响应：对方的地址列表"""
        peers_list = payload.get('peers', [])
        log.debug(f"收到 {peer.node_id} 的 'addr' 响应，包含 {len(peers_list)} 个地址")
        self.address_manager.add_peers_from_list(peers_list)

    async def handle_notify_new_peer(self, peer: Peer, payload: dict):
        """处理 'notify_new_peer' 广播：一个新节点"""
        peer_info = payload.get('peer_info')
        if peer_info:
            log.debug(f"收到 {peer.node_id} 广播的新节点： {peer_info.get('node_id')}")
            self.address_manager.add_peers_from_list([peer_info])

    # --- 原有业务逻辑处理器 ---

    async def handle_get_best_tip(self, peer: Peer, payload: dict):
        # tip = self.blockchain.get_best_tip()
        # response_payload = {'tip_info': tip, 'request_id': payload.get('request_id')}
        # await peer.send_message('best_tip_response', response_payload)
        pass # 暂时禁用

    async def handle_get_block_info(self, peer: Peer, payload: dict):
        # ...
        pass # 暂时禁用

    async def handle_notify_new_block_header(self, peer: Peer, payload: dict):
        # ...
        pass # 暂时禁用

    async def handle_unknown(self, peer: Peer, payload: dict):
        msg_type = peer.node_id
        log.warning(f"收到来自 {msg_type} 的未知消息类型")