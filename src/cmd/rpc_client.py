"""
    rpc client
"""
import logging
import requests
import json
log = logging.getLogger(__name__)

class RpcClient:
    def __init__(self, rpc_server_url: str):
        self.rpc_server_url = rpc_server_url

    def make_rpc_request(self, method, endpoint, params=None, data=None):
        """Universal RPC request function (synchronous)"""
        url = f"{self.rpc_server_url}{endpoint}"
        try:
            response = requests.request(method, url, params=params, json=data)
            if response.status_code == 200:
                return response.json()
            else:
                log.error(f"endpoint:{endpoint},method:{method} Error: {response.status_code} - {response.text}")
                return None
        except requests.exceptions.ConnectionError as e:
            log.error(f"Connection failed: {e}")
            return None

    def get_balance(self, address):
        """Get address balance"""
        result = self.make_rpc_request("GET", f"/address/{address}/balance")
        return result

    def send_raw_transaction(self, hex_data):
        """Send raw transaction"""
        data = {"hex": hex_data}
        result = self.make_rpc_request("POST", "/tx/send", data=data)
        return result

    def get_best_tip(self):
        """Get best block tip"""
        result = self.make_rpc_request("GET", "/block/best-tip")
        return result

    def get_latest_blocks(self, count):
        """Get latest blocks"""
        if not 1 <= count <= 50:
            raise ValueError("Count must be between 1 and 50.")
        result = self.make_rpc_request("GET", f"/block/latest/{count}")
        return result

    def get_block_by_height(self, height):
        """Get block by height"""
        result = self.make_rpc_request("GET", f"/block/height/{height}")
        return result

    def get_block_by_hash(self, block_hash):
        """Get block by hash"""
        result = self.make_rpc_request("GET", f"/block/hash/{block_hash}")
        return result

    def get_transaction_by_hash(self, tx_hash):
        """Get transaction by hash"""
        result = self.make_rpc_request("GET", f"/tx/{tx_hash}")
        return result

    def get_transactions_by_address(self, address):
        """Get transactions by address"""
        result = self.make_rpc_request("GET", f"/address/{address}/txs")
        return result

    def get_utxos_by_address(self, address):
        """Get UTXOs by address"""
        result = self.make_rpc_request("GET", f"/address/{address}/utxos")
        return result

    def get_utxo_info(self,tx_hash,index):
        return  self.make_rpc_request("GET",endpoint=f'/utxo/{tx_hash}/{index}')