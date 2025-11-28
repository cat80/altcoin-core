import asyncio
import io
import logging

from .event_bus import EventBus
from .peer_manager import PeerManager
from .peer import Peer
from core.blockchain import Blockchain
from mempool.mempool import Mempool
from typing import Optional
from core import Block
import asyncio
from core.transaction import Transaction

log = logging.getLogger(__name__)


class ProtocolHandler:
    def __init__(self, event_bus: EventBus, blockchain: Blockchain,
                 peer_manager: PeerManager, mempool: Mempool,
                 address_manager: 'AddressManager'):
        self.event_bus = event_bus
        self.blockchain = blockchain
        self.peer_manager = peer_manager
        self.mempool = mempool
        self.address_manager = address_manager
        self.is_syncing = False  # 新增：同步状态标志

        # 订阅 Peer 发来的所有消息
        self.event_bus.subscribe('network_message_received', self.on_message_received)
        # ProtocolHandler 也订阅 peer_connected 以触发 PULL
        self.event_bus.subscribe('peer_connected', self.on_peer_connected)
        # 订阅连接失败事件
        self.event_bus.subscribe('peer_connection_failed', self.on_peer_connection_failed)
        # 订阅连接断开事件
        self.event_bus.subscribe('peer_disconnected', self.on_peer_disconnected)

    async def on_peer_connected(self, peer: Peer):
        """
        [EventBus 调用] 这是“统一逻辑”的 PULL 部分：
        1. 标记节点成功 (DB)
        2. 主动拉取地址 (PULL)
        """
        # 1. 标记成功 (DB)
        conn_info = peer.get_connection_info()
        if conn_info and conn_info['host']:
            self.address_manager.mark_peer_success(
                conn_info['node_id'], conn_info['host'], conn_info['port']
            )

        # 2. 主动拉取地址 (PULL)
        log.debug(f"向新节点 {peer.node_id} 发送 'getaddr' 请求")
        # await peer.send_message('getaddr', {})

    async def on_peer_connection_failed(self, node_id: str):
        """[EventBus 调用] 当连接失败时标记节点"""
        log.debug(f"标记节点 {node_id} 连接失败")
        self.address_manager.mark_peer_failed(node_id)

    async def on_peer_disconnected(self, peer: Peer):
        """[EventBus 调用] 当连接断开时标记节点"""
        log.debug(f"标记节点 {peer.node_id} 连接断开")
        self.address_manager.mark_peer_disconnected(peer.node_id)

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

        # 1. 优先返回当前已连接的节点
        active_peers = self.peer_manager.get_active_peers_info()

        # 2. 如果不足，从数据库获取高质量节点补充
        num_needed = 25 - len(active_peers)
        if num_needed > 0:
            # 排除自己和已在列表中的节点
            exclude_ids = {p['node_id'] for p in active_peers}
            exclude_ids.add(peer.node_id)

            db_peers = self.address_manager.get_peers_to_try(
                limit=num_needed,
                exclude_ids=exclude_ids
            )
            peers_list = active_peers + db_peers
        else:
            peers_list = active_peers

        await peer.send_message('addr', {'peers': peers_list})

    async def handle_addr(self, peer: Peer, payload: dict):
        """处理 'addr' 响应：对方的地址列表"""
        peers_list = payload.get('peers', [])
        log.debug(f"收到 {peer.node_id} 的 'addr' 响应，包含 {len(peers_list)} 个地址")
        self.address_manager.add_peers_from_list(peers_list)

    async def handle_ping(self, peer: Peer, payload):
        await peer.send_message("pong")

    async def handle_pong(self, peer: Peer, payload):
        self.address_manager.update_peer_score(peer.node_id, 1)

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
        pass  # 暂时禁用

    # --- 区块同步核心处理器 ---

    async def handle_notify_new_block_header(self, peer: Peer, payload: dict):
        """处理新区块头的广播，这是同步的入口点"""
        header_info = payload.get('header')
        if not header_info:
            return

        log.debug(f"收到来自 {peer.node_id} 的新区块头广播: 高度 {header_info['height']}")
        
        # --- 修改：增加同步状态检查 ---
        if self.is_syncing:
            log.debug("正在同步中，暂时忽略新的区块头通知。")
            return

        local_tip = self.blockchain.get_best_tip()

        if not local_tip or header_info['total_work'] <= local_tip['total_work']:
            log.debug("收到的区块头工作量不优，忽略。")
            return

        if self.blockchain.block_index.get_header_info(bytes.fromhex(header_info['block_hash'])):
            log.debug("已知的区块头，忽略。")
            return

        if header_info['prev_block_hash'] == local_tip['block_hash'].hex():
            log.info(f"区块头是主链的直接后继，准备请求完整区块 {header_info['block_hash']}")
            await peer.send_message("get_block", {'hash': header_info['block_hash']})
        else:
            log.info(f"收到的区块头领先较多，准备启动 Headers-First 同步流程。")
            # --- 修改：进入同步状态 ---
            self.is_syncing = True
            await self.event_bus.publish('sync_started')
            asyncio.create_task(self.start_headers_sync(peer))

    async def handle_get_headers(self, peer: Peer, payload: dict):
        """响应 get_headers 请求"""
        locator_hex = payload.get('locator', [])
        hash_stop_hex = payload.get('hash_stop')
        locator = [bytes.fromhex(h) for h in locator_hex]
        log.debug(f"定位列表长度:{len(locator)}")
        common_ancestor_hash = None
        for h in locator:
            if self.blockchain.block_index.get_header_info(h):
                common_ancestor_hash = h
                break

        if not common_ancestor_hash:
            log.debug(f'未找到共同祖先')
            return

        headers_to_send = []
        start_height = self.blockchain.block_index.get_header_info(common_ancestor_hash)['height'] + 1
        log.debug(f'找到共同祖先区块:{common_ancestor_hash.hex()},开始返回区块高度:{start_height} 开始收集区块头')
        for height in range(start_height, start_height + 2000):
            header_info = self.blockchain.block_index.get_header_by_height(height)
            if not header_info: break
            header_info['block_hash'] = header_info['block_hash'].hex()
            header_info['prev_block_hash'] = header_info['prev_block_hash'].hex()
            header_info['merkle_root'] = header_info['merkle_root'].hex()
            headers_to_send.append(header_info)
            if header_info['block_hash'] == hash_stop_hex: break

        if headers_to_send:
            log.debug(f"回复 {peer.node_id} 的 get_headers 请求，发送 {len(headers_to_send)} 个区块头")
            await peer.send_message('headers_list', {'headers': headers_to_send})

    async def handle_headers_list(self, peer: Peer, payload: dict):
        """处理 headers_list 响应，这是同步的关键"""
        headers = payload.get('headers', [])
        if not headers:
            log.info("Headers 同步完成。")
            # --- 修改：退出同步状态 ---
            if self.is_syncing:
                self.is_syncing = False
                await self.event_bus.publish('sync_finished')
            return

        log.info(f"收到来自 {peer.node_id} 的 {len(headers)} 个区块头，开始验证并下载...")

        for header in headers:
            block_hash = bytes.fromhex(header['block_hash'])
            if not self.blockchain.block_index.get_header_info(block_hash):
                await peer.send_message("get_block", {'hash': header['block_hash']})

        if len(headers) == 2000:
            log.info("可能还有更多区块头，继续同步...")
            await self.start_headers_sync(peer)
        else:
            # --- 修改：如果这是最后批次的区块头，则同步完成 ---
            if self.is_syncing:
                self.is_syncing = False
                await self.event_bus.publish('sync_finished')


    async def handle_get_block(self, peer: Peer, payload: dict):
        """响应 get_block 请求"""
        block_hash = bytes.fromhex(payload.get('hash'))
        log.debug(f"收到来自 {peer.node_id} 的 get_block 请求: {block_hash.hex()}")

        block_info = self.blockchain.block_index.get_header_info(block_hash)
        if block_info:
            block = self.blockchain.block_storage.read_block(block_info['file_index'], block_info['file_offset'])
            if block:
                await peer.send_message('block_info', {'block_data': block.serialize().hex()})

    async def handle_block_info(self, peer: Peer, payload: dict):
        """处理收到的完整区块信息"""
        block_hex = payload.get('block_data')
        if not block_hex: return
        stream = io.BytesIO(bytes.fromhex(block_hex))
        block = Block.deserialize(stream)
        log.debug(f'收到block:{block.hash().hex()}')
        
        # --- 恢复简单逻辑 ---
        if self.blockchain.add_block(block):
            best_tip = self.blockchain.get_best_tip()
            if best_tip['block_hash'] == block.hash():
                log.debug(f'收到最新验证区块，区块高度:{best_tip["height"]}，发布区块验证通知')
                asyncio.create_task(self.event_bus.publish("block_validated", best_tip))

    async def handle_notify_new_block(self, peer: Peer, payload: dict):
        """
        处理旧的、广播完整区块的消息（为了兼容性或简化测试）。
        已弃用。
        """
        block_data_hex = payload.get('block')
        if not block_data_hex: return

        block_bytes = io.BytesIO(bytes.fromhex(block_data_hex))
        block = Block.deserialize(block_bytes)
        log.debug(f'收到完整区块广播: {block.hash().hex()}，来自节点: {peer.get_connection_info()}')

        self.blockchain.add_block(block=block)

    # --- 辅助方法 ---

    async def start_headers_sync(self, peer: Peer):
        """与一个 Peer 启动 Headers-First 同步流程"""
        locator_hashes = self.blockchain.block_index.get_locator_hashes()
        if not locator_hashes:
            # 如果无法获取定位哈希，则无法同步，退出同步状态
            if self.is_syncing:
                self.is_syncing = False
                await self.event_bus.publish('sync_finished')
            return

        log.debug(f"向 {peer.get_connection_info()} 发送 get_headers 请求")
        await peer.send_message('get_headers', {
            'locator': [h.hex() for h in locator_hashes],
            'hash_stop': (b'\x00' * 32).hex()
        })


    async def handle_notify_new_tx(self,peer:Peer, payload:dict):
        tx_bytes = bytes.fromhex(payload.get('tx'))
        tx = Transaction.deserialize(io.BytesIO(tx_bytes))
        log.debug(f'收到节点:{peer.get_connection_info()}，广播新交易:{tx.hash().hex()}')
        await self.event_bus.publish('recv_new_tx',tx)

    async def handle_manbc(self,peer:Peer,payload:dict):
        # 手动广播
        log.info(f'recv from {peer.get_connection_info()}:{payload}')
        
    async def handle_unknown(self, peer: Peer, payload: dict):
        msg_type = peer.node_id
        log.warning(f"收到来自 {peer.get_connection_info()} 的未知消息类型")