import os.path

import requests
import logging
import json
from decimal import Decimal, getcontext

from core.transaction import Transaction,   TxOut,TxIn
from core.wallet import Wallet
# 设置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
from config import setup_logging
setup_logging()
log = logging.getLogger(__name__)
from typing import List
# 设置Decimal精度
getcontext().prec = 20

# RPC服务器的地址
RPC_SERVER_URL = "http://127.0.0.1:8088"

# http://0.0.0.0:8088

class RpcCmd:
    def __init__(self):
        self.running = True
        self.wallet = None
        self.wallet_dir =f'/mnt/d/prj/web3/altcoin-core/nodes-data/wallet-key/'
    #     12T36cYGFN8yZqpDX3w5e8HucsEpfPDGsb

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
    def cmd_wallets(self,args):
        for item in os.listdir(self.wallet_dir):
            wall_file = os.path.join(self.wallet_dir,item)
            try:
                wallet = Wallet.from_file(wall_file)
                result = self._make_rpc_request("GET", f"/address/{wallet.get_address()}/balance")
                print(f'filename:{item},address:{wallet.get_address()},balance:{result}')
            except Exception as e :
                log.debug(f'wallet {item} invalid.')

    def cmd_getbalance(self, args):
        """查询地址余额"""
        if len(args) < 1:
            log.info("Usage: getbalance <address>")
            return
        address = args[0]
        result = self._make_rpc_request("GET", f"/address/{address}/balance")
        if result:
            log.info(json.dumps(result, indent=2))

    def cmd_getbesttip(self, args):
        """获取主链最新区块信息"""
        result = self._make_rpc_request("GET", "/block/best-tip")
        if result:
            log.info(json.dumps(result, indent=2))

    def cmd_getblockbyheight(self, args):
        """通过高度查询区块"""
        if len(args) < 1:
            log.info("Usage: getblockbyheight <height>")
            return
        try:
            height = int(args[0])
            result = self._make_rpc_request("GET", f"/block/height/{height}")
            if result:
                log.info(json.dumps(result, indent=4))
        except ValueError:
            log.error("Invalid height format. Must be an integer.")

    def cmd_sendtx(self, args):
        """创建并发送一笔交易"""
        try:
            from_address = input('  From Address: ')
            private_key_path = input('  Private Key File Path: ')
            to_address = input('  To Address: ')
            amount_str = input('  Amount (in ALT): ')
            fee_str = input('  Fee (in  ALT): ')

            amount = Decimal(amount_str) * 10**8  # 转换为satoshi
            fee = int(fee_str)
            # 12T36cYGFN8yZqpDX3w5e8HucsEpfPDGsb
            # to:1FYDejzwBhVAnyqRTB35meTZBiTzEdcD8M
            # 1. 加载钱包
            private_key_path = os.path.join(self.wallet_dir,private_key_path)
            self.wallet = Wallet.from_file(private_key_path)
            if self.wallet.get_address() != from_address:
                log.error("Address does not match the private key.")
                return

            # 2. 获取UTXOs
            utxos_data = self._make_rpc_request("GET", f"/address/{from_address}/utxos")
            if not utxos_data:
                log.error("Failed to get UTXOs or no UTXOs found for the address.")
                return
            log.debug(f'有效的utxo:{len(utxos_data)}')
            # 3. 构建交易
            total_input_value = 0
            inputs : List[TxIn] = []

            for utxo in utxos_data:
                inputs.append(TxIn(bytes.fromhex(utxo['tx_hash']), utxo['output_index'],b''))
                total_input_value += utxo['value']
                if total_input_value >= amount+fee:
                    break
                log.info(f'utxo add to tx in：{utxo}')
            
            if total_input_value < amount + fee:
                log.error(f"Insufficient funds. Required: {amount + fee}, Available: {total_input_value}")
                return

            outputs = [
                TxOut(int(amount),to_address.encode('utf8'))
            ]
            
            # 计算找零
            change = total_input_value - int(amount) - fee
            if change > 0:
                outputs.append(TxOut(change, from_address.encode('utf8')))

            # 4. 签名交易
            tx = Transaction(1,inputs, outputs,0)
            signed_inx  = []
            for item in inputs:

                sign = self.wallet.sign(tx.serialize(for_signing=True))
                signed_inx.append(
                    TxIn(
                        item.prev_tx_hash,
                        item.prev_tx_out_index,
                        sign +  self.wallet.public_key.to_string()
                    )
                )
            tx = Transaction(1, signed_inx, outputs, 0)

            # 5. 发送交易
            raw_tx_hex = tx.serialize().hex()
            send_result = self._make_rpc_request("POST", "/tx/send", data={"hex": raw_tx_hex})
            if send_result:
                log.info("Transaction sent successfully:")
                log.info(json.dumps(send_result, indent=2))

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
