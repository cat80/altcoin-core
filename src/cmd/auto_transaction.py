import logging
import os.path
import random

from cmd.rpc_client import  RpcClient
from core.wallet import Wallet
from cmd.send_transaction import SendTransaction
import threading
import time
log = logging.getLogger(__name__)
class AutoTransaction:
    def __init__(self,rpc_client:RpcClient,wallets_dir:str,interval=None,tx_amount=None,fee_amount=None):
        self.rpc_client = rpc_client
        self.send_tx = SendTransaction(rpc_client)
        self.wallets_dir = wallets_dir
        self.interval = interval or [5,60]
        self.tx_amount = tx_amount or [0.1,10]
        self.fee_amount = fee_amount or [0.001, 0.02]
        self.auto_tx_event =threading.Event()
        self.lock = threading.Lock()
        self.work_thread = None
    def start(self):
        if not os.path.isdir(self.wallets_dir):
            log.info(f'wallets dir not exists ,terminate auto tx')
            return
        self.auto_tx_event.clear()

        if self.lock.acquire(timeout=0):

            self.work_thread = threading.Thread(target=self.on_auto_tx)
            self.work_thread.start()
            self.lock.release()
        else:
            log.info('Auto transaction is already running, skipping start.')
        # threading.Thread(target= self.on_auto_tx).start()

    def stop(self):
        if self.work_thread and self.work_thread.is_alive():
            log.info('Setting stop event for auto transaction.')
            self.auto_tx_event.set()
            self.work_thread.join()
            self.work_thread = None
            log.info('Auto transaction stopped.')
        else:
            log.info('Auto transaction is not running')
    def restart(self):
        self.stop()
        self.start()
    def load_wallets(self):
        wallets  = []
        for wallet_file in os.listdir(self.wallets_dir):
            try:
                wallets.append(Wallet.from_file(os.path.join(self.wallets_dir,wallet_file)))
            except Exception as e:
                log.error(f'log wallet [{wallet_file}] fail:{e}')
        return wallets

    def on_auto_tx(self):

        log.info('start auto tx...')
        if self.lock.acquire(timeout=0):
            try:
                wallets = self.load_wallets()
                if not wallets or len(wallets) < 2:
                    log.info(f'wallet amount least more than 2')
                    return
                while  not  self.auto_tx_event.is_set():
                    send_wallet,recv_wallet = random.sample(wallets,k=2)
                    send_amount = round(  random.uniform(self.tx_amount[0],self.tx_amount[1]),6)
                    fee_amount = round( random.uniform(self.fee_amount[0],self.fee_amount[1]),6)
                    log.debug(f'from {send_wallet.get_address()} to {recv_wallet.get_address()},amount:{send_amount},fee:{fee_amount}')
                    self.send_tx.send_tx(send_wallet,recv_wallet.get_address(),send_amount,fee_amount,f'auto tx,time:{time.time()}')
                    self.auto_tx_event.wait(random.uniform(self.interval[0],self.interval[1]))
            except Exception as e:
                log.error(f'auto tx occur error:{e}')
                log.debug(f'exception:{e}',exc_info=True)
            finally:
                log.debug('auto tx is canceled or stopped')
                self.lock.release() # release lock
        else:
            log.info('aut  tx is running...')
