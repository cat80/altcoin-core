"""
    节点的命令处理，包括打包交易，查看询节点状态等
"""
import datetime
import logging


from core.blockchain import Blockchain
from core import BlockHeader
from p2p.peer_manager import PeerManager
from p2p.event_bus import EventBus
import asyncio
log = logging.getLogger(__name__)
# from p2p.address_manager import AddressManager
from consensus.miner import Miner

class PeerCmdHandler:
    def __init__(self,block_chian:Blockchain,peer_manager:PeerManager,

                 event_bus:EventBus,address_manager,miner:Miner):
        self.block_chian = block_chian
        self.peer_manager = peer_manager
        self.event_bus = event_bus
        self.input_task = self.cmd_input_handler()
        self.miner = miner
        asyncio.create_task(self.input_task)

        self.address_manager = address_manager
    def input_text_to_arr(self, txt:str, arr_len=2):
        txt_arr = txt.split(' ')
        ret_arr = [ '' for _ in range(arr_len) ]
        for _ in range(arr_len):
            if _ < len(txt_arr):
                ret_arr[_] = txt_arr[_]
            else:
                ret_arr [_] = ''
        if len(txt_arr) > arr_len:
            ret_arr[-1] =  " ".join(  txt_arr[arr_len-1:])
        return ret_arr
    async def cmd_p2p_bc(self,txt):
        """
            p2p广播
        :param txt:
        :return:
        """
        cmd_arr =self.input_text_to_arr(txt,3)
        log.info(f'广播消息:{cmd_arr[2]}')
        await self.peer_manager.broadcast("ping",{"msg":cmd_arr[2]})

    async def cmd_p2p_info(self,txt):
        """
            p2p连接信息
        :return:
        """
        log.info(f'节点id:{self.peer_manager.my_node_id},监听端口:{self.peer_manager.my_listen_port}')
        log.info(f'coinbase地址:{self.miner.coinbase_address}')
        log.info(f"当前连接数:{len(self.peer_manager.peers)}")
        log.info(f"数据库保存连接数:{self.address_manager.get_record_count()}")

    async def cmd_mc_tip(self,txt):
        # 查询节点主链
        print(self.miner.blockchain.get_best_tip())
        self.show_block_info(self.miner.blockchain.get_best_tip())

    async def cmd_mc_info(self,txt):
        # 查询节点主链 [ block_hash  prev_block_hash  merkle_root  00000019f7a67d94e42a2fd0b261833976eaa621afe097029545a460c4e509bd]-区块高度[10]信息:{'block_hash': b'\x00\x00\x00\x19\xf7\xa6}\x94\xe4*/\xd0\xb2a\x839v\xea\xa6!\xaf\xe0\x97\x02\x95E\xa4`\xc4\xe5\t\xbd', 'prev_block_hash': b'\x00\x00\x00"t\x11P\x8f\xbf\xb3\x10]\x9d\x80\xfd\xa9\x19F\x13\xed\xfc\r)q\x1c\xf98\xd0\x87Fv[', 'merkle_root': b'\xb4L\xf1\x0e\xe4y\x9d\xed\xe2\xd9\xf6\x8f\xd2\xef\xe4\x89\xde\xd7\xd9\xcfL;\xc0a\xc6\x93\xf6\x8f\x18\x95\x9e$', 'timestamp': 1763368232, 'bits': 491618097, 'nonce': 45961944, 'height': 10, 'total_work': 609633107.4121194, 'status': 1, 'file_index': 0, 'file_offset': 2497}
        best_tip =  self.miner.blockchain.get_best_tip()
        block_height = best_tip['height']
        block_hash = best_tip['block_hash'].hex()
        prev_block_hash = best_tip['prev_block_hash'].hex()
        create_time = datetime.datetime.fromtimestamp(best_tip['timestamp']).strftime('%y-%m-%d %H:%M:%s')
        log.info(f'当前主链高度:{block_height},hash:{block_hash},prev：{prev_block_hash},create time:{create_time},total_work: {best_tip["total_work"]}')
    def show_block_info(self, block_header:dict):
        if not block_header:
            log.info(f'区块不存在')
        else:
            log.info(f'查询区块[{block_header["block_hash"].hex()}]-区块高度[{block_header["height"]}]信息:{block_header}')

            block_info = self.block_chian.block_storage.read_block(block_header['file_index'],  block_header['file_offset'])
            print(f'该区块共有:{len(block_info.transactions)}笔交易')
            for index, trans in enumerate(block_info.transactions):
                log.info(f"trans index:{index},{trans}")
                log.info(f"trans index:{index},{trans.to_json_text()}")
                # log.info(f'index:{index},trans:{trans.}')
    async def cmd_mc_h(self,txt):
        txt_arr = self.input_text_to_arr(txt, 3)
        block_height =  txt_arr[2]
        if not block_height:
            log.info(f'请输入有效的区块高度：{block_height}')

        self.show_block_info(self.miner.blockchain.block_index.get_header_by_height(int(block_height)))
    async def cmd_mc_block(self,txt):
        # 查询节点主链
        txt_arr = self.input_text_to_arr(txt,3)
        block_hash  = bytes.fromhex( txt_arr[2])
        block_header =  self.miner.blockchain.block_index.get_header_info(block_hash)

        self.show_block_info(block_header)

    async def cmd_unknwn(self,txt):
        log.info(f'未知道的cmd 命令：{txt}')

    async def cmd_input_handler(self):
        while True:
            try:
                input_txt = await asyncio.to_thread(input,'>')
                txt_arr =self.input_text_to_arr(input_txt,3)
                cmd_invoke_method = getattr(self,f"cmd_{txt_arr[0]}_{txt_arr[1]}",self.cmd_unknwn)
                await cmd_invoke_method(input_txt)
            except Exception as e:
                log.debug("命令执行出错",exc_info=True)