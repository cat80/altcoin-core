"""
    发起一笔交易
"""
import logging
import os.path
from config import setup_logging
from cmd.rpc_client import RpcClient
from decimal import Decimal
from core.wallet import Wallet
log = logging.getLogger(__name__)
from typing import List
from core import Transaction,TxIn,TxOut

class SendTransaction:
    def __init__(self,rpc_client:RpcClient):
        self.rpc_client = rpc_client
    def build_tx(self)->Transaction:
        # 构建交易
        pass
    def send_tx(self, wallet:Wallet, to_address, alt_amount, fee_alt_amount, op_return_data:str=None):
        try:
            amount = Decimal(alt_amount) * 10 ** 8  # 转换为satoshi
            fee = Decimal(fee_alt_amount) * 10 ** 8
            # 12T36cYGFN8yZqpDX3w5e8HucsEpfPDGsb
            # to:1FYDejzwBhVAnyqRTB35meTZBiTzEdcD8M
            # 1.get address
            amount = int(amount)
            fee = int(fee)
            from_address = wallet.get_address()

            # 2. get UTXOs
            utxos_data = self.rpc_client.get_utxos_by_address(from_address)
            if not utxos_data:
                log.error("Failed to get UTXOs or no UTXOs found for the address.")
                return None
            log.debug(f'valid utxo len:{len(utxos_data)}')
            # 3. 构建交易
            total_input_value = 0
            inputs: List[TxIn] = []

            for utxo in utxos_data:
                inputs.append(TxIn(bytes.fromhex(utxo['tx_hash']), utxo['output_index'], b''))
                total_input_value += utxo['value']
                log.debug(f'utxo add to tx in：{utxo}')
                if total_input_value >= amount + fee:
                    break

            log.debug(f'add utxo :{len(inputs)}')
            if total_input_value < amount + fee:
                log.error(f"Insufficient funds. Required: {amount + fee}, Available: {total_input_value}")
                return None

            outputs = [
                TxOut(int(amount), to_address.encode('utf8'))
            ]

            # calc change
            change = total_input_value - int(amount) - fee
            if change > 0:
                outputs.append(TxOut(change, from_address.encode('utf8')))
            if op_return_data and not op_return_data.strip():
                op_return_data = op_return_data.strip()
                op_return_data = op_return_data.encode('utf8')
            else:
                op_return_data = None
            # 4. sign tx
            tx = Transaction(1, inputs, outputs, 0, op_return_data)
            signed_inx = []
            for item in inputs:
                sign = wallet.sign(tx.serialize(for_signing=True))
                signed_inx.append(
                    TxIn(
                        item.prev_tx_hash,
                        item.prev_tx_out_index,
                        sign + wallet.public_key.to_string()
                    )
                )
            tx = Transaction(1, signed_inx, outputs, 0, op_return_data)

            # 5. send raw tx
            raw_tx_hex = tx.serialize().hex()
            send_result = self.rpc_client.send_raw_transaction( raw_tx_hex)
            if send_result:
                log.info(f"Transaction sent successfully:{send_result}")
            return send_result
        except Exception as e:
            log.error(f'转账失败,{e}')
            log.debug(f'exception:{e}',exc_info=True)

if __name__ == "__main__":
    setup_logging()
    wallet_dir = f'/mnt/d/prj/web3/altcoin-core/nodes-data/wallet-key/'
    # wallet = Wallet.from_file(f'{wallet_dir}node_key80')
    # print(wallet.get_address())
    # mantest-112HCT1pLPTCH5SV9roNRpnHUJSjTfg8Qn
    # node_key80-14LSV8drtBfizdpJt41VafxDRzGRvm96wj
    send_wallet = Wallet.from_file(os.path.join(wallet_dir,'node_key80-14LSV8drtBfizdpJt41VafxDRzGRvm96wj'))
    recv_wallet = Wallet.from_file(os.path.join(wallet_dir,'mantest-112HCT1pLPTCH5SV9roNRpnHUJSjTfg8Qn'))
    rpc = RpcClient('http://127.0.0.1:8080')
    utxos = rpc.get_utxos_by_address('14LSV8drtBfizdpJt41VafxDRzGRvm96wj')
    not_found_utxo = []
    for item in utxos:
        utxo = rpc.get_utxo_info(item['tx_hash'],item['output_index'])
        if utxo['result'] == 0:
            not_found_utxo.append(f'not found.{item}->{utxo}')
    print(f'not found utxo:{len(not_found_utxo)}')
    print(not_found_utxo)
    utxo = rpc.get_utxo_info("602f1bf261782e24a26afb39b1f8a25a89626b9eab556747e00396972e3e869a", 0)
    print(utxo)
    send_tx = SendTransaction(rpc_client=rpc)

    result = send_tx.send_tx(send_wallet,recv_wallet.get_address(),2,0.001,'man test')
    print(result)