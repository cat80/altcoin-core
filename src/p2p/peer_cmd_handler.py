"""
    节点的命令处理，包括打包交易，查看询节点状态等
"""
import logging


from core.blockchain import Blockchain
from p2p.peer_manager import PeerManager
from p2p.event_bus import EventBus
import asyncio
log = logging.getLogger(__name__)
from p2p.address_manager import AddressManager
class PeerCmdHandler:
    def __init__(self,block_chian:Blockchain,peer_manager:PeerManager,

                 event_bus:EventBus,address_manager:AddressManager):
        self.block_chian = block_chian
        self.peer_manager = peer_manager
        self.event_bus = event_bus
        self.input_task = self.cmd_input_handler()
        asyncio.create_task(self.input_task)

        self.address_manager = address_manager

    async def cmd_input_handler(self):
        while True:
            try:
                input_txt = await asyncio.to_thread(input,'>')
                txt_arr =input_txt.split(" ")
                cmd = txt_arr[0]
                if cmd == "bc":
                    msg = cmd
                    if len(txt_arr) >1:
                        msg = txt_arr[-1]
                    log.debug(f"广播消息:{msg}")
                    await self.peer_manager.broadcast("ping",{"msg":msg})
                elif cmd =="stat":
                    log.debug(f'当前连接数:{len(self.peer_manager.peers)}')
                    db_peers = self.address_manager.get_peers_to_try(100)
                    log.debug(f'数据库存储节点数:{len(db_peers)}')
                    pass
                elif cmd == 'allpeers':
                    log.debug(f"{self.address_manager.get_all_peers()}")
                else:
                    log.debug(f'未知的命令:{cmd}')
            except Exception as e:
                log.debug("命令执行出错",exc_info=True)