import asyncio
import logging
import threading
from typing import Optional
import random

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
        self.mining_lock = asyncio.Lock()
        self.extra_nonce = 0
        self.is_syncing = False

        # 订阅事件
        self.event_bus.subscribe('block_validated', self.update_mining_state)
        self.event_bus.subscribe('new_transaction_received', self.update_mining_state)
        self.event_bus.subscribe('sync_started', self.on_sync_started)
        self.event_bus.subscribe('sync_finished', self.on_sync_finished)
        
        self.stop_mining_event = threading.Event()
        asyncio.create_task(self.update_mining_state())

    async def on_sync_started(self, *args):
        """[事件回调] 当同步开始时，更新状态并停止挖矿"""
        log.info("同步开始，将暂停挖矿...")
        self.is_syncing = True
        await self.update_mining_state()

    async def on_sync_finished(self, *args):
        """[事件回调] 当同步完成时，更新状态并恢复挖矿"""
        log.info("同步完成，将恢复挖矿...")
        self.is_syncing = False
        await self.update_mining_state()

    async def update_mining_state(self, *args):
        """
        统一的挖矿状态更新方法，确保线程安全。
        根据 self.is_syncing 决定是启动还是停止挖矿。
        """
        async with self.mining_lock:
            # 停止当前的挖矿任务
            if self.mining_task and not self.mining_task.done():
                self.stop_mining_event.set()
                try:
                    await asyncio.wait_for(self.mining_task, timeout=1.0)
                except (asyncio.CancelledError, asyncio.TimeoutError):
                    pass # 忽略异常，目标就是停止它
                log.debug("旧的挖矿任务已停止。")

            # 如果不处于同步状态，则启动新的挖矿任务
            if not self.is_syncing:
                log.info("启动新的挖矿任务...")
                self.stop_mining_event.clear()
                self.mining_task = asyncio.create_task(self._run_mining_loop())
            else:
                log.info("当前正在同步，挖矿任务保持暂停。")

    async def create_next_block(self, prev_header_info: dict,transactions :list[Transaction] ) -> Block:
        block_height = prev_header_info['height'] +1
        
        self.extra_nonce += 1
        coinbase_unlocking_script_prefix = str(block_height).encode('utf-8') + b':'
        coinbase_data = coinbase_unlocking_script_prefix + self.cionbase_data + str(self.extra_nonce).encode('utf-8') + str(random.randint(0,10000000)).encode('utf-8')

        coinbase_tx = Transaction(1, [TxIn.create_coinbase_txin(coinbase_data)], [TxOut(BlockValidator.get_block_reward(block_height) + BlockValidator.check_non_coinbase_tx_and_get_fee(transactions,self.blockchain.chain_state) , self.coinbase_address.encode('utf8'))], lock_time=0)
        transactions.insert(0,coinbase_tx)

        tx_hashes = [tx.hash() for tx in transactions]
        merkle_root = MerkleTree(tx_hashes).root
        
        bits = self.blockchain.block_index.calculate_required_bits(block_height, prev_header_info)
        
        header = BlockHeader(
            version=1,
            prev_block_hash=prev_header_info["block_hash"],
            merkle_root=merkle_root,
            timestamp=int(time.time()),
            bits=bits,
            nonce=0
        )

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
            prev_header_info = self.blockchain.get_best_tip()
            txs = self.mempool.get_local_pack_transactions()

            new_block = await self.create_next_block(prev_header_info, txs)
            
            if self.stop_mining_event.is_set():
                log.info("挖矿被中止，放弃找到的区块。")
                return

            if new_block:
                log.info('挖矿成功，尝试增加到本地主链')
                if self.blockchain.add_block(block=new_block):
                    log.info("本地主链增加成功")
                    best_tip = self.blockchain.get_best_tip()
                    # --- 修复：使用 asyncio.create_task 避免死锁 ---
                    asyncio.create_task(self.event_bus.publish("block_validated", best_tip))
                else:
                    log.info('本地主链增加失败，可能因为链已更新，等待下一次挖矿信号。')
            else:
                log.info(f'挖矿失败或被终止')

        except asyncio.CancelledError:
            log.info("挖矿任务被取消。")
        except Exception as e:
            log.debug("挖矿循环出错:", exc_info=True)
            log.error(f"挖矿循环错误: {e}")

    @staticmethod
    def __do_minning_cpu_loop(block:Block,event:threading.Event):
        """
            这里是真实开启挖矿
        :param block:
        :param event:
        :return:
        """
        log.debug(f'[挖矿线程]开始挖矿,prev block{block.header.prev_block_hash.hex()}')
        header = block.header
        target = BlockValidator.bits_to_target(header.bits)

        while int.from_bytes(header.hash(), 'big') >= target:
            if header.nonce % 100000 == 0:
                if event.is_set():
                    log.debug('[挖矿线程]收到中止挖矿通知,退出挖矿...')
                    return None
            header = dataclasses.replace(header, nonce=header.nonce + 1)
            
        log.debug(f'[挖矿线程] 找到新的区块，区块hash:{header.hash().hex()},nonce:{header.nonce} ')
        return header.nonce