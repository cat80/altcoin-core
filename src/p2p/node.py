import asyncio
import logging

from .peer_manager import PeerManager
# init log
log  = logging.getLogger(__name__)
class P2PNode:
    def __init__(self, peer_manager: PeerManager, seed_nodes: list):
        self.peer_manager = peer_manager
        self.seed_nodes = seed_nodes
        self.server = None

    async def start(self, host: str, port: int):
        # 1. 启动服务器，被动接受连接
        self.server = await asyncio.start_server(
            self.on_incoming_connection, host, port
        )
        log.debug(f"Node listening on {host}:{port}")

        # 2. 异步启动客户端，主动连接到种子节点
        for node in self.seed_nodes:
            asyncio.create_task(
                self.initiate_outgoing_connection(node['host'], node['port'])
            )

        # 保持服务器运行
        async with self.server:
            await self.server.serve_forever()

    async def on_incoming_connection(self, reader, writer):
        """[回调] 当有新连接进来时"""
        addr = writer.get_extra_info('peername')
        log.debug(f"Accepted incoming connection from {addr}")
        # 将连接交给 PeerManager 处理握手和后续
        await self.peer_manager.start_handshake(
            reader, writer, is_initiator=False
        )

    async def initiate_outgoing_connection(self, host: str, port: int):
        """[任务] 主动连接到其他节点"""
        try:
            reader, writer = await asyncio.open_connection(host, port)
            addr = writer.get_extra_info('peername')
            log.debug(f"Established outgoing connection to {addr}")
            # 将连接交给 PeerManager 处理握手和后续
            await self.peer_manager.start_handshake(
                reader, writer, is_initiator=True
            )
        except Exception as e:
            log.debug(f"Failed to connect to {host}:{port}: {e}")
