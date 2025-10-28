import logging

from .event_bus import EventBus
from .peer_manager import PeerManager
from .peer import Peer
from core.blockchain import Blockchain
from core.block_validator import BlockValidator # 假设用于快速验证
from core.block import Block # 假设用于反序列化
from mempool.mempool import Mempool
log = logging.getLogger(__name__)
class ProtocolHandler:
    def __init__(self, event_bus: EventBus, blockchain: Blockchain,
                 peer_manager: PeerManager, mempool: Mempool):
        self.event_bus = event_bus
        self.blockchain = blockchain
        self.peer_manager = peer_manager
        self.mempool = mempool

        # 订阅 Peer 发来的所有消息
        self.event_bus.subscribe('network_message_received', self.on_message_received)

    async def on_message_received(self, peer: Peer, message: dict):
        """主消息调度器"""

        # 1. 检查这是否是对我们某个请求的“响应”
        if self.peer_manager.resolve_request(message):
            return # PeerManager 已处理，无需后续操作

        # 2. 如果不是响应，它就是一个“新请求”，正常处理
        msg_type = message.get('type')
        payload = message.get('payload', {})

        handler_method = getattr(self, f"handle_{msg_type}", self.handle_unknown)
        await handler_method(peer, payload)

    # --- 业务逻辑处理器 ---

    async def handle_get_best_tip(self, peer: Peer, payload: dict):
        tip = self.blockchain.get_best_tip()
        # 将 request_id 传回去，以便对方的 PeerManager 能够解析
        response_payload = {'tip_info': tip, 'request_id': payload.get('request_id')}
        await peer.send_message('best_tip_response', response_payload)

    async def handle_get_block_info(self, peer: Peer, payload: dict):
        block_hash_hex = payload.get('hash_hex')
        # (假设 block_storage 有按哈希读取的方法)
        block = self.blockchain.block_storage.read_block_by_hash(bytes.fromhex(block_hash_hex))

        response_payload = {
            'block_data': block.serialize() if block else None,
            'request_id': payload.get('request_id')
        }
        await peer.send_message('block_info_response', response_payload)

    async def handle_notify_new_block_header(self, peer: Peer, payload: dict):
        """
        处理来自网络的新区块头 (最复杂的业务)
        """
        header_data = payload['header']
        # (假设 BlockHeader 可以从 data 反序列化)
        # header = BlockHeader.deserialize(header_data)
        # header_hash = header.hash()
        header_hash = b'mock_hash_from_header_data' # 模拟哈希

        # 1. 检查是否已知
        if self.blockchain.block_index.get_header_info(header_hash):
            return # 已知，忽略

        # 2. 快速验证 (例如 PoW)
        # if not BlockValidator.check_block_header(header):
        #    return # 无效，忽略 (或惩罚)

        log.debug(f"New valid header {header_hash.hex()} from {peer.node_id}. Requesting full block...")

        try:
            # 3. **核心业务**: "同步"请求完整区块
            response_payload = await self.peer_manager.request_data(
                peer,
                'get_block_info',
                {'hash_hex': header_hash.hex()}
            )

            if not response_payload.get('block_data'):
                raise Exception("Peer did not return block data")

            # 4. 反序列化并添加到本地链
            block = Block.deserialize(response_payload['block_data'])
            if self.blockchain.add_block(block):
                log.debug(f"Successfully added block {block.hash().hex()} from {peer.node_id}")
                # add_block 成功后，应发布 'block_validated' 事件
                # (这个可以由 add_block 内部实现，或在这里实现)
                await self.event_bus.publish('block_validated', block)
            else:
                log.debug(f"Failed to add block {block.hash().hex()} (validation failed)")

        except Exception as e:
            log.debug(f"Failed to get or add block {header_hash.hex()}: {e}")

    async def handle_unknown(self, peer: Peer, payload: dict):
        log.debug(f"Received unknown message type from {peer.node_id}")
