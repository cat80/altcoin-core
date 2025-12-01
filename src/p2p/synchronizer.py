import asyncio
import logging
import io
from typing import Optional, List
from .peer import Peer
from core import Blockchain, Block
from.event_bus import EventBus
log = logging.getLogger(__name__)

SYNC_TIMEOUT = 30.0  # 同步操作的超时时间（秒）


class Synchronizer:
    def __init__(self, blockchain: Blockchain, peer_manager: 'PeerManager',event_bus:EventBus):
        self.blockchain = blockchain
        self.peer_manager = peer_manager
        self.event_bus = event_bus
        self.is_syncing = False
        self.sync_peer: Optional[Peer] = None
        self.sync_task: Optional[asyncio.Task] = None

    def on_peer_disconnected(self, peer: Peer):
        """如果断开的是同步节点，则中止同步。"""
        if self.sync_peer and self.sync_peer.node_id == peer.node_id:
            log.warning(f"同步节点 {peer.node_id} 断开连接，中止同步。")
            self.abort_sync()

    def abort_sync(self):
        """中止当前的同步过程。"""
        if not self.is_syncing:
            return
        log.info("中止同步流程。")
        if self.sync_task and not self.sync_task.done():
            self.sync_task.cancel()

        self.is_syncing = False
        self.sync_peer = None
        self.sync_task = None
        asyncio.create_task(self.event_bus.publish('sync_finished'))

    async def on_new_block_header(self, peer: Peer, header_info: dict):
        """处理新区块头通知，决定是否启动同步。"""
        if self.is_syncing:
            log.debug("正在同步中，忽略新的区块头通知。")
            return

        local_tip = self.blockchain.get_best_tip()
        if not local_tip or header_info['total_work'] <= local_tip['total_work']:
            log.debug(f'接收的区块工作量低于本地，忽略。')
            return
        block_hash_hex = header_info['block_hash']
        if self.blockchain.block_index.get_header_info(bytes.fromhex(header_info['block_hash'])):
            log.debug(f'本地索引中该区块已经存在，忽略。')
            return
        if header_info['prev_block_hash'] == local_tip['block_hash'].hex():
            log.info(f"收到主链后继区块头 {block_hash_hex[:10]}...，直接请求下载。")
            try:
                response_message = await peer.reqeust_wait_response('get_block', {'hash': block_hash_hex})
                block_hex = response_message.payload.get('block_data')
                if block_hex:
                    # 注意：这里我们不设置 is_syncing，因为这是一个快速、原子性的操作
                    if await self.on_block_received(peer, block_hex):
                        # 发布广播区块验证广播，重启挖矿 block_validated
                        await self.event_bus.publish('block_validated',self.blockchain.get_best_tip())
                else:
                    log.warning(f"节点 {peer.node_id} 未能提供所请求的后继区块 {block_hash_hex[:10]}...")
            except Exception as e:
                log.error(f"快速获取区块失败: {e}")
        else:
        # 决定启动同步
            self.is_syncing = True
            self.sync_peer = peer
            log.info(f"检测到需要同步，选择节点 {peer.get_connection_info()} 作为同步源。")
            await self.event_bus.publish('sync_started')
            # 创建并启动同步任务
            self.sync_task = asyncio.create_task(self._run_sync_flow())

    async def _run_sync_flow(self):
        """完整的 Headers-First 同步流程，包含超时。"""
        try:
            await asyncio.wait_for(self._headers_first_sync(), timeout=SYNC_TIMEOUT)
        except asyncio.TimeoutError:
            log.warning(f"与节点 {self.sync_peer.node_id} 的同步任务整体超时。")
            if self.sync_peer:
                self.peer_manager.update_peer_score(self.sync_peer.node_id, -20)  # 超时扣分
        except asyncio.CancelledError:
            log.info("同步任务被手动取消。")
        except Exception as e:
            log.error(f"同步流程中发生未知错误: {e}", exc_info=True)
        finally:
            self.abort_sync()

    async def _headers_first_sync(self):
        """Headers-First 同步的核心逻辑。"""
        while True:
            locator_hashes = self.blockchain.block_index.get_locator_hashes()
            if not locator_hashes:
                log.error("无法获取定位哈希，无法启动同步。")
                return

            log.debug(f"向 {self.sync_peer.node_id} 请求区块头...")
            header_response = await self.sync_peer.reqeust_wait_response(
                'get_headers',
                {'locator': [h.hex() for h in locator_hashes], 'hash_stop': (b'\x00' * 32).hex()}
            )
            headers = header_response.payload.get('headers', [])
            if not headers:
                log.info("收到空的区块头列表，同步完成。")
                break

            log.info(f"收到 {len(headers)} 个区块头，开始请求下载...")
            for header in headers:
                block_hash_hex = header['block_hash']
                log.debug(f"请求下载区块: {block_hash_hex}")
                response_message = await self.sync_peer.reqeust_wait_response('get_block', {'hash': block_hash_hex},60)

                block_hex = response_message.payload.get('block_data')
                if not block_hex:
                    log.warning(f"节点 {self.sync_peer.node_id} 未能提供区块 {block_hash_hex}。")
                    raise Exception("Failed to get block data")

                await self.on_block_received(self.sync_peer, block_hex)

            if len(headers) < 2000:
                log.info("收到最后一批区块头，同步完成。")
                await self.event_bus.publish('block_validated',self.blockchain.get_best_tip())
                break

    async def on_headers_received(self, peer: Peer, headers: List[dict]):
        # 这个方法在新的 request-response 模式下不再被直接使用，
        # 因为 _headers_first_sync 会直接处理响应。
        # 但我们保留它以防未来需要。
        pass

    async def on_block_received(self, peer: Peer, block_hex: str):
        """处理收到的完整区块，并添加到区块链中。"""
        try:
            stream = io.BytesIO(bytes.fromhex(block_hex))
            block = Block.deserialize(stream)
            log.debug(f'正在处理区块: {block.hash().hex()}')

            if self.blockchain.add_block(block):
                best_tip = self.blockchain.get_best_tip()
                if best_tip and best_tip['block_hash'] == block.hash():
                    log.debug(f'新区块 {block.hash().hex()} 已成功添加并成为主链顶端。')
                    # 在同步流程中，我们不在这里广播，由同步器统一管理
                return True
            else:
                log.warning(f"区块 {block.hash().hex()} 添加失败。")
        except Exception as e:
            log.error(f"处理接收到的区块时出错: {e}", exc_info=True)
