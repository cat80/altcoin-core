import logging
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import uvicorn
import io

from core.blockchain import Blockchain
from core.transaction import Transaction
from p2p.event_bus import EventBus
from mempool.mempool import Mempool
from indexer.model import AddressUTXO, BlockInfo, TransactionInfo, AddressTransaction
from storage.sql_alchemy_wrapper import SQLAlchemyWrapper

log = logging.getLogger(__name__)

class RawTx(BaseModel):
    """用于接收裸交易数据的模型"""
    hex: str

class RpcServer:

    def __init__(self, rpc_port: int, blockchain: Blockchain, mempool: Mempool,
                 indexer_db: SQLAlchemyWrapper):
        self.port = rpc_port
        self.blockchain = blockchain
        self.mempool = mempool
        self.app = FastAPI()
        self.db = indexer_db
        @self.app.post("/tx/send")
        async def send_raw_transaction(raw_tx: RawTx):
            try:
                tx_bytes = bytes.fromhex(raw_tx.hex)
                tx = Transaction.deserialize(io.BytesIO(tx_bytes))
                tx_hash = tx.hash()
                if await self.mempool.add_transaction(tx):
                    return {"status": "success", "txid": tx_hash.hex()}
                else:
                    # add_transaction 返回 False 通常意味着交易无效或已存在
                    return {"status": "fail","message":"Transaction is invalid or already in mempool"}
                    raise HTTPException(status_code=400, detail="Transaction is invalid or already in mempool.")
            except (ValueError, TypeError, IndexError) as e:
                # 捕获反序列化或十六进制转换错误
                raise HTTPException(status_code=400, detail=f"Invalid raw transaction format: {e}")
            except Exception as e:
                log.error(f"Error processing transaction: {e}", exc_info=True)
                raise HTTPException(status_code=500, detail="Internal server error")

        @self.app.get("/block/best-tip")
        async def get_best_tip():
            with self.db.get_session() as session:
                latest_block = session.query(BlockInfo).order_by(BlockInfo.height.desc()).first()
                if not latest_block:
                    raise HTTPException(status_code=404, detail="No blocks found in index.")
                return {
                    "height": latest_block.height,
                    "hash": latest_block.hash,
                    "timestamp": latest_block.timestamp
                }

        @self.app.get("/block/latest/{count}")
        async def get_latest_blocks(count: int):
            if not 1 <= count <= 50:
                raise HTTPException(status_code=400, detail="Count must be between 1 and 50.")
            with self.db.get_session() as session:
                blocks = session.query(BlockInfo).order_by(BlockInfo.height.desc()).limit(count).all()
                return [{
                    "height": b.height, "hash": b.hash, "timestamp": b.timestamp, "tx_count": b.tx_count
                } for b in blocks]

        async def get_block_details(block: BlockInfo, session):
            """辅助函数，用于获取完整的区块详情"""
            transactions = session.query(TransactionInfo).filter_by(block_hash=block.hash).all()
            # 在实际应用中，这里可以进一步查询交易的输入输出来丰富信息
            return {
                "header": {
                    "height": block.height, "hash": block.hash, "prev_hash": block.prev_hash,
                    "merkle_root": block.merkle_root, "timestamp": block.timestamp
                },
                "transactions": [{"tx_hash": tx.tx_hash, "fee": tx.fee} for tx in transactions]
            }

        @self.app.get("/block/height/{height}")
        async def get_block_by_height(height: int):
            with self.db.get_session() as session:
                block = session.query(BlockInfo).filter_by(height=height).first()
                if not block:
                    raise HTTPException(status_code=404, detail="Block not found.")
                return await get_block_details(block, session)

        @self.app.get("/block/hash/{b_hash}")
        async def get_block_by_hash(b_hash: str):
            with self.db.get_session() as session:
                block = session.query(BlockInfo).filter_by(hash=b_hash).first()
                if not block:
                    raise HTTPException(status_code=404, detail="Block not found.")
                return await get_block_details(block, session)

        @self.app.get("/tx/{tx_hash}")
        async def get_transaction_by_hash(tx_hash: str):
            with self.db.get_session() as session:
                tx = session.query(TransactionInfo).filter_by(tx_hash=tx_hash).first()
                if not tx:
                    raise HTTPException(status_code=404, detail="Transaction not found.")
                return {
                    "tx_hash": tx.tx_hash,
                    "block_hash": tx.block_hash,
                    "block_height": tx.block_height,
                    "timestamp": tx.timestamp,
                    "fee": tx.fee
                }

        @self.app.get("/address/{address}/txs")
        async def get_transactions_by_address(address: str):
            with self.db.get_session() as session:
                # 这里可以添加分页逻辑
                addr_txs = session.query(AddressTransaction).filter_by(address=address).order_by(AddressTransaction.block_height.desc()).limit(100).all()
                return [{
                    "tx_hash": at.tx_hash,
                    "block_height": at.block_height,
                    "role": at.role
                } for at in addr_txs]

        @self.app.get("/address/{address}/utxos")
        async def get_utxos_by_address(address: str):
            with self.db.get_session() as session:
                try:
                    utxos = session.query(AddressUTXO).filter_by(
                        address=address
                    ).all()

                    return [{
                        "tx_hash": utxo.tx_hash,
                        "output_index": utxo.output_index,
                        "value": utxo.value
                    } for utxo in utxos]
                except Exception as e:
                    log.error(f"Error querying UTXOs for address {address}: {e}", exc_info=True)
                    raise HTTPException(status_code=500, detail="Internal server error")

        @self.app.get("/address/{address}/balance")
        async def get_balance_by_address(address: str):
            with self.db.get_session() as session:
                try:
                    utxos = session.query(AddressUTXO).filter_by(address=address).all()
                    balance = sum(utxo.value for utxo in utxos)
                    return {"address": address, "balance": balance, "unit": "satoshi"}
                except Exception as e:
                    log.error(f"Error querying balance for address {address}: {e}", exc_info=True)
                    raise HTTPException(status_code=500, detail="Internal server error")

    async def run(self):
        """以编程方式启动 FastAPI 服务器"""
        config = uvicorn.Config(self.app, host="0.0.0.0", port=self.port, log_level="info")
        server = uvicorn.Server(config)
        log.info(f"RPC server started on http://0.0.0.0:{self.port}")
        await server.serve()
