import os.path
from pickle import FRAME

import requests
import logging
import json
from decimal import Decimal, getcontext

from core.transaction import Transaction,   TxOut,TxIn
from core.wallet import Wallet
# 设置日志
from config import setup_logging
setup_logging()
log = logging.getLogger(__name__)
from typing import List
from cmd.send_transaction import SendTransaction
from cmd.auto_transaction import AutoTransaction
from cmd.rpc_client import RpcClient
# 设置Decimal精度
getcontext().prec = 20
import threading

# RPC服务器的地址
RPC_SERVER_URL = "http://127.0.0.1:8080"

# http://0.0.0.0:8088

class RpcCmd:
    def __init__(self):
        self.running = True
        self.wallet = None
        self.wallet_dir =f'/mnt/d/prj/web3/altcoin-core/nodes-data/wallet-key/'
    #     12T36cYGFN8yZqpDX3w5e8HucsEpfPDGsb
        self.rpc_client =  RpcClient(RPC_SERVER_URL)
        self.send_tx = SendTransaction(self.rpc_client)
        self.auto_tx = AutoTransaction(self.rpc_client,self.wallet_dir)

    def _make_rpc_request(self, method, endpoint, params=None, data=None):
        """通用RPC请求函数 (同步)"""
        url = f"{RPC_SERVER_URL}{endpoint}"
        try:
            response = requests.request(method, url, params=params, json=data)
            if response.status_code == 200:
                return response.json()
            else:
                log.error(f"Error: {response.status_code} - {response.text}")
                return None
        except requests.exceptions.ConnectionError as e:
            log.error(f"Connection failed: {e}")
            return None

    def cmd_gen(self,args):
        wallet_name = input('Input wallet name：')
        wallet = Wallet.generate()
        save_filename = os.path.join(self.wallet_dir,f"{wallet_name}-{wallet.get_address()}.pem")
        wallet.save_to_file(save_filename)
        log.info(f'wallet generated success save to file:{save_filename}')

    def cmd_getbalance(self, args):
        """查询地址余额"""
        if len(args) < 1:
            log.info("Usage: getbalance <address>")
            return
        address = args[0]
        result =self.rpc_client.get_balance(address)
        if result:
            log.info(json.dumps(result, indent=2))

    def cmd_getbesttip(self, args):
        """获取主链最新区块信息"""
        result = self.rpc_client.get_best_tip()
        if result:
            log.info(json.dumps(result, indent=2))

    def cmd_getblockbyheight(self, args):
        """通过高度查询区块"""
        if len(args) < 1:
            log.info("Usage: getblockbyheight <height>")
            return
        try:
            height = int(args[0])
            result = self.rpc_client.get_block_by_height(height)
            if result:
                log.info(json.dumps(result, indent=4))
        except ValueError:
            log.error("Invalid height format. Must be an integer.")
    def cmd_autotx(self,args):
        # 自动发起交易
        self.auto_tx.start()

    def cmd_stopautotx(self,args):
        self.auto_tx.stop()

    def cmd_sendtx(self, args):
        """创建并发送一笔交易"""
        try:
            from_address = input('  From Address: ')
            private_key_path = input('  Private Key File Path: ')
            to_address = input('  To Address: ')
            amount_str = input('  Amount (in ALT): ')
            fee_str = input('  Fee (in  ALT): ')

            tx_msg = input('trans msg:')

            private_key_path = os.path.join(self.wallet_dir,private_key_path)
            self.wallet = Wallet.from_file(private_key_path)
            if self.wallet.get_address() != from_address:
                log.error("Address does not match the private key.")
                return
            amount = Decimal(amount_str)
            fee = Decimal(fee_str)
            result = self.send_tx.send_tx(self.wallet,to_address,amount,fee,tx_msg)
            # 2. 获取UTX
            log.debug(f'trans info:{result}')
        except FileNotFoundError:
            log.error(f"Private key file not found at: {private_key_path}")
        except Exception as e:
            log.error(f"An error occurred: {e}", exc_info=True)

    def cmd_help(self, args):
        """显示帮助信息"""
        log.info("Available commands:")
        log.info("  getbalance <address>              - Get balance for an address.")
        log.info("  getbesttip                        - Get the latest block tip.")
        log.info("  getblockbyheight <height>         - Get block details by height.")
        log.info("  sendtransaction                   - Interactively create and send a transaction.")
        log.info("  exit                              - Exit the RPC client.")
        log.info("  help                              - Show this help message.")

    def cmd_exit(self, args):
        """退出客户端"""
        self.running = False
        log.info("Exiting...")

    def run(self):
        """主循环，处理用户输入"""
        log.info("RPC Client started. Type 'help' for commands.")
        while self.running:
            try:
                input_txt = input('rpc> ')
                if not input_txt.strip():
                    continue
                
                parts = input_txt.strip().split()
                command = parts[0].lower()
                args = parts[1:]

                cmd_method = getattr(self, f"cmd_{command}", None)
                if cmd_method:
                    cmd_method(args)
                else:
                    log.warning(f"Unknown command: {command}")

            except (EOFError, KeyboardInterrupt):
                self.running = False
                log.info("\nExiting...")
            except Exception as e:
                log.error(f"An error occurred in the command loop: {e}", exc_info=True)

def main():
    rpc_cmd = RpcCmd()
    rpc_cmd.run()

if __name__ == "__main__":
    main()
