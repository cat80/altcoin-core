import asyncio
import logging
import threading
from typing import Optional

from core.blockchain import Blockchain
from utils import MerkleTree
from core import BlockHeader,BlockValidator,Transaction,TxIn,TxOut,Block
from mempool.mempool import Mempool
from p2p.event_bus import EventBus
import time
import dataclasses

log = logging.getLogger(__name__)

class Miner:
    def __init__(self, event_bus: EventBus, blockchain: Blockchain,
                 mempool: Mempool, coinbase_address: str):
        self.event_bus = event_bus
        self.blockchain = blockchain
        self.mempool = mempool
        self.cionbase_data = b''
        self.coinbase_address = coinbase_address
        self.mining_task: Optional[asyncio.Task] = None

        # 订阅事件以控制挖矿
        self.event_bus.subscribe('block_validated', self.on_new_tip)
        self.event_bus.subscribe('new_transaction_received', self.on_new_tip) # (Mempool应发布此事件)
        # 线程同步
        self.stop_mining_event = threading.Event()
        # 启动初始挖矿
        asyncio.create_task(  self.start_mining())


    async def start_mining(self):
        """启动一个新的挖矿任务"""
        self.stop_mining_event.set()

        if self.mining_task and not self.mining_task.done():
            log.debug('等待挖矿任务结束...')
            try:
                await self.mining_task
            except asyncio.CancelledError:
                log.debug('挖矿任务取消成功...')
            log.debug('挖矿任务结束结束')
        log.info("Starting new mining task...")
        self.stop_mining_event.clear()
        self.mining_task = asyncio.create_task(self._run_mining_loop())

    async def on_new_tip(self, *args):
        """[事件回调] 当链顶改变或有新交易时"""
        log.debug("New tip or transaction received. Restarting miner...")
        await self.start_mining()

    async def create_next_block(self, prev_header_info: dict,transactions :list[Transaction] ) -> Block:
        block_height = prev_header_info['height'] +1
        coinbase_unlcking_script_prefix = str(block_height).encode('utf-8') + b':'
        coinbase_data = coinbase_unlcking_script_prefix + self.cionbase_data
        coinbase_tx = Transaction(1, [TxIn.create_coinbase_txin(coinbase_data)], [TxOut(BlockValidator.get_block_reward(block_height), self.coinbase_address.encode('utf8'))], lock_time=0)
        # 写入coinbse交易
        transactions.insert(0,coinbase_tx)

        #计算merkleroot
        tx_hashes = [tx.hash() for tx in transactions]
        merkle_root = MerkleTree(tx_hashes).root
        bits = self.blockchain.block_index.calculate_required_bits(prev_header_info['height'] + 1)
        header = BlockHeader(
            version=1,
            prev_block_hash=prev_header_info["block_hash"],
            merkle_root=merkle_root,
            timestamp=int(time.time()),
            bits=bits,
            nonce=0
        )

        # Mine the block (find a valid nonce)
        target = BlockValidator.bits_to_target(bits)

        #  这里是cpu任务需求to_thread 新开线程计算，防止任务阻塞
        block =  Block(header, transactions)
        find_nonce = await asyncio.to_thread(Miner.__do_minning_cpu_loop,block,self.stop_mining_event)
        if find_nonce:
            block.header = dataclasses.replace(block.header,nonce=find_nonce)
            return Block(block.header,transactions)
        else:
            return None

    async def _run_mining_loop(self):
        """实际的挖矿循环"""
        log.debug('开始挖矿...')
        try:
            # 1. 准备新区块
            prev_header_info = self.blockchain.get_best_tip()
            txs = self.mempool.get_local_pack_transactions()


            new_block = await self.create_next_block(prev_header_info, txs)
            if new_block:
                log.info('挖矿成功，尝试增加到本地主链')
                if self.blockchain.add_block(block=new_block):
                    log.info("本地主链增加成功")
                    # 发布block_validated消息，重新挖矿以及广播消息
                    best_tip = self.blockchain.get_best_tip()
                    asyncio.create_task(  self.event_bus.publish("block_validated", best_tip))
                    return
                else:
                    log.info('本地主链增加失败，重新开始挖矿')
                    # 重新开始挖矿
                    asyncio.create_task(  self.start_mining())
                    return
            else:
                log.info(f'挖矿失败或终止探矿')

        except asyncio.CancelledError:
            print("Mining task cancelled.")
        except Exception as e:
            asyncio.create_task(self.start_mining())
            log.debug("Exception details for mining loop error:", exc_info=True)
            log.error(f"Mining loop error: {e}")


    @staticmethod
    def __do_minning_cpu_loop(block:Block,event:threading.Event):
        """
            这里是真实开启挖矿
        :param block:
        :param event:
        :return:
        """
        log.debug(f'[挖矿线程]开始挖矿,prev block{block.header.prev_block_hash.hex()}')
        nonce = 0
        header = block.header

        target = BlockValidator.bits_to_target(header.bits)

        #  这里是cpu任务需求to_thread 新开线程计算，防止任务阻塞

        while int.from_bytes(header.hash(), 'big') >= target:  # Simplified mining
            # header.nonce += 1
            if header.nonce % 100000 ==0:
                if event.is_set():
                    log.debug('[挖矿线程]收到中止挖矿通知,退出挖矿...')
                    return None

            header = dataclasses.replace(header, nonce=header.nonce + 1)
        # 找到目标值
        log.debug(f'[挖矿线程] 找到新的区块，区块hash:{header.hash().hex()},nonce:{header.nonce} ')
        return header.nonce