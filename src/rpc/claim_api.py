import logging
import time
import os
import random
from typing import Optional

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from core.blockchain import Blockchain
from core.transaction import Transaction, TxIn, TxOut
from core.wallet import Wallet
from mempool.mempool import Mempool
from indexer.model import AddressUTXO, ExplorerClaimHistory
from storage.sql_alchemy_wrapper import SQLAlchemyWrapper

log = logging.getLogger(__name__)


class ClaimRequest(BaseModel):
    address: str


class ClaimAPI:
    def __init__(self, db: SQLAlchemyWrapper, mempool: Mempool, blockchain: Blockchain):
        # 1. 保存依赖项
        self.db = db
        self.mempool = mempool
        self.blockchain = blockchain

        # 2. 读取配置
        self.recv_wallets = os.getenv('RPC_CLAIM_RECV_WALLETS',
                                      '18DqR4mFpptWAE8dvPDBDwWhAcrDZZh61T,112HCT1pLPTCH5SV9roNRpnHUJSjTfg8Qn').split(
            ',')
        wallet_file = os.getenv('RPC_CLAIM_SEND_WALLET_FILE')
        self.ip_limit = int(os.getenv('RPC_CLAIM_SEND_IP_LIMIT', 10))
        self.day_limit = int(os.getenv('RPC_CLAIM_SEND_DAY_LIMIT', 20))
        self.amount_range = [float(x) for x in os.getenv('RPC_CLAIM_SEND_AMOUNT', '0.1,2').split(',')]

        # 3. 加载钱包
        if not wallet_file or not os.path.exists(wallet_file):
            log.error(f"Faucet wallet file not configured or does not exist: {wallet_file}.Use empty wallet.")
            # raise ValueError("Faucet feature cannot be initialized: Wallet file configuration error.")
            self.wallet = Wallet.generate()
        else:
            self.wallet = Wallet.from_file(wallet_file)
        log.info(f"Faucet feature loaded, sending address: {self.wallet.get_address()}")

        # 4. 创建并设置路由
        self.router = APIRouter(prefix='/rpc/claim')
        self._setup_routes()

    def _setup_routes(self):
        @self.router.get("/address")
        async def get_claim_addresses():
            return {"addresses": self.recv_wallets}

        @self.router.post("/claimcoin")
        async def claim_coin(req: ClaimRequest, request: Request):
            client_ip = request.client.host
            if not Wallet.is_valid_wallet_address(req.address):
                return  {
                    "status":"fail",
                    "detail":"Claim wallet address is not valid.Please input correct wallet address or selected default wallet address."
                }
            with self.db.get_session() as session:
                ip_claim_count = session.query(ExplorerClaimHistory).filter(
                    ExplorerClaimHistory.ip_address == client_ip,
                    ExplorerClaimHistory.timestamp >= (time.time() - 24 * 3600)
                ).count()
                if ip_claim_count >= self.ip_limit:
                    raise HTTPException(status_code=429,
                                        detail=f"Your IP has reached the daily claim limit ({self.ip_limit}).")

                day_claim_count = session.query(ExplorerClaimHistory).filter(
                    ExplorerClaimHistory.timestamp >= (time.time() - 24 * 3600)
                ).count()
                if day_claim_count >= self.day_limit:
                    raise HTTPException(status_code=429,
                                        detail=f"The faucet has reached its daily total claim limit ({self.day_limit}). Please try again tomorrow.")

            try:
                amount_to_send = random.uniform(self.amount_range[0], self.amount_range[1])
                tx = self._build_and_sign_tx(req.address, amount_to_send)
                if not tx:
                    raise HTTPException(status_code=500,
                                        detail="Failed to build transaction. The faucet may have insufficient funds.")
            except Exception as e:
                log.error(f"Error building faucet transaction: {e}", exc_info=True)
                raise HTTPException(status_code=500, detail=f"Internal Server Error: {e}")

            if not await self.mempool.add_transaction(tx):
                raise HTTPException(status_code=500,
                                    detail="Failed to submit transaction to the mempool. Please try again later.")

            tx_hash = tx.hash().hex()
            with self.db.get_session() as session:
                history_record = ExplorerClaimHistory(
                    ip_address=client_ip,
                    recv_address=req.address,
                    timestamp=int(time.time()),
                    tx_hash=tx_hash,
                    amount=int(amount_to_send * 10 ** 8)
                )
                session.add(history_record)
                session.commit()

            return {"status": "success", "txid": tx_hash, "amount": amount_to_send}

    def _get_internal_utxos(self, address: str) -> list:
        mempool_spent_utxos = self.mempool.spent_utxos
        with self.db.get_session() as session:
            utxos_from_db = session.query(AddressUTXO).filter_by(address=address).all()
            available_utxos = []
            for utxo in utxos_from_db:
                utxo_ref = f"{utxo.tx_hash}:{utxo.output_index}"
                if utxo_ref not in mempool_spent_utxos:
                    available_utxos.append({
                        "tx_hash": utxo.tx_hash,
                        "output_index": utxo.output_index,
                        "value": utxo.value
                    })
            return available_utxos

    def _build_and_sign_tx(self, to_address: str, amount_alt: float) -> Optional[Transaction]:
        from_address = self.wallet.get_address()
        amount = int(amount_alt * 10 ** 8)
        fee = int(0.001 * 10 ** 8)
        utxos = self._get_internal_utxos(from_address)

        total_input_value = 0
        inputs: list[TxIn] = []
        for utxo in utxos:
            inputs.append(TxIn(bytes.fromhex(utxo['tx_hash']), utxo['output_index'], b''))
            total_input_value += utxo['value']
            if total_input_value >= amount + fee:
                break

        if total_input_value < amount + fee:
            log.error(f"Faucet has insufficient funds. Required: {amount + fee}, Available: {total_input_value}")
            return None

        outputs = [TxOut(amount, to_address.encode('utf8'))]
        change = total_input_value - amount - fee
        if change > 0:
            outputs.append(TxOut(change, from_address.encode('utf8')))

        tx_for_signing = Transaction(1, inputs, outputs, 0)

        signed_inputs = []
        for tx_in in inputs:
            signature = self.wallet.sign(tx_for_signing.serialize(for_signing=True))
            signed_inputs.append(
                TxIn(tx_in.prev_tx_hash, tx_in.prev_tx_out_index, signature + self.wallet.public_key.to_string()))

        return Transaction(1, signed_inputs, outputs, 0)
