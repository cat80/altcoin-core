import logging
import time
from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel
import uvicorn
import io
from sqlalchemy import func, desc, or_
from collections import defaultdict

from core.blockchain import Blockchain
from core.transaction import Transaction,TxIn,TxOut
from mempool.mempool import Mempool
from indexer.model import AddressUTXO, BlockInfo, TransactionInfo, AddressTransaction
from storage.sql_alchemy_wrapper import SQLAlchemyWrapper

log = logging.getLogger(__name__)

class RawTx(BaseModel):
    """用于接收裸交易数据的模型"""
    hex: str

def decode_op_return(hex_data: str | None) -> str | None:
    """尝试将 OP_RETURN 的 hex 数据解码为 UTF-8 字符串，失败则返回原始 hex。"""
    if not hex_data:
        return None
    try:
        return bytes.fromhex(hex_data).decode('utf-8')
    except (UnicodeDecodeError, ValueError):
        return hex_data

class RpcServer:

    def __init__(self, rpc_port: int, blockchain: Blockchain, mempool: Mempool,
                 indexer_db: SQLAlchemyWrapper):
        self.port = rpc_port
        self.blockchain = blockchain
        self.mempool = mempool
        self.app = FastAPI()
        self.db = indexer_db

        # 统一的搜索入口
        @self.app.get("/search/{hashid}")
        async def search_by_hash_or_id(hashid: str):
            with self.db.get_session() as session:
                # 尝试作为区块哈希搜索
                block_by_hash = session.query(BlockInfo).filter_by(hash=hashid).first()
                if block_by_hash:
                    return {"result": 1, "type": "block", "data": f"/block/hash/{hashid}"}

                # 尝试作为交易哈希搜索
                tx_by_hash = session.query(TransactionInfo).filter_by(hash=hashid).first()
                if tx_by_hash:
                    return {"result": 1, "type": "tx", "data": f"/tx/{hashid}"}

                # 尝试作为区块高度搜索
                if hashid.isdigit():
                    block_by_height = session.query(BlockInfo).filter_by(height=int(hashid)).first()
                    if block_by_height:
                        return {"result": 1, "type": "block", "data": f"/block/height/{hashid}"}
                
                # 尝试作为地址搜索 (简单检查是否存在于地址交易表中)
                address_check = session.query(AddressTransaction).filter_by(address=hashid).first()
                if address_check:
                    return {"result": 1, "type": "address", "data": f"/address/{hashid}/txs"}

            return {"result": 0, "type": "not_found"}

        # 交易相关
        @self.app.post("/tx/send")
        async def send_raw_transaction(raw_tx: RawTx):
            try:
                tx_bytes = bytes.fromhex(raw_tx.hex)
                tx = Transaction.deserialize(io.BytesIO(tx_bytes))
                tx_hash = tx.hash()
                if await self.mempool.add_transaction(tx):
                    return {"status": "success", "txid": tx_hash.hex()}
                else:
                    # 提供更具体的错误信息
                    # 注意：这里为了安全，不应暴露过多内部细节，但可以区分“已存在”和“无效”
                    if tx_hash in self.mempool.transactions:
                         detail = "Transaction already in mempool."
                    else:
                         detail = "Transaction is invalid (e.g., double spend or incorrect signature)."
                    raise HTTPException(status_code=400, detail=detail)
            except (ValueError, TypeError, IndexError) as e:
                raise HTTPException(status_code=400, detail=f"Invalid raw transaction format: {e}")
            except Exception as e:
                log.error(f"Error processing transaction: {e}", exc_info=True)
                raise HTTPException(status_code=500, detail="Internal server error")

        @self.app.get("/tx/{tx_hash}")
        async def get_transaction_by_hash(tx_hash: str):
            with self.db.get_session() as session:
                tx_info = session.query(TransactionInfo).filter_by(hash=tx_hash).first()
                if not tx_info:
                    raise HTTPException(status_code=404, detail="Transaction not found.")

                inputs = session.query(AddressTransaction).filter_by(tx_hash=tx_hash, role='input').all()
                outputs = session.query(AddressTransaction).filter_by(tx_hash=tx_hash, role='output').all()

                return {
                    "hash": tx_info.hash,
                    "block_hash": tx_info.block_hash,
                    "block_height": tx_info.block_height,
                    "timestamp": tx_info.timestamp,
                    "tx_index": tx_info.tx_index,
                    "fee": tx_info.fee,
                    "input_amount": tx_info.input_amount,
                    "output_amount": tx_info.output_amount,
                    "tx_amount": tx_info.tx_amount,
                    "input_count": tx_info.input_count,
                    "output_count": tx_info.output_count,
                    "op_return_data": decode_op_return(tx_info.op_return_data),
                    "inputs": [{"address": i.address, "value": -i.value} for i in inputs],
                    "outputs": [{"address": o.address, "value": o.value} for o in outputs]
                }

        @self.app.get("/utxo/{tx_hash}/{index}")
        def get_utxo(tx_hash: str, index: int):
            tx_in = TxIn(bytes.fromhex(tx_hash), index, b'')
            tx_out = self.blockchain.chain_state.get_utxo(tx_in)
            if tx_out:
                return {
                    'result': 1,
                    'address': tx_out.locking_script.decode('utf8'),
                    'value': tx_out.value
                }
            else:
                return {
                    'result': 0
                }

        @self.app.get("/tx/large/{period}/{page}")
        async def get_large_transactions(period: str, page: int, page_size: int = Query(20, ge=1, le=100)):
            if period not in ['d1']: # d1 for 1 day
                 raise HTTPException(status_code=400, detail="Invalid period. Use 'd1' for last 24 hours.")
            
            with self.db.get_session() as session:
                seconds_in_period = 24 * 3600 # 1 day
                start_ts = int(time.time()) - seconds_in_period
                
                query = session.query(TransactionInfo).filter(
                    TransactionInfo.timestamp >= start_ts,
                    TransactionInfo.tx_amount > 0
                )
                
                total_count = query.count()
                txs = query.order_by(desc(TransactionInfo.tx_amount)).offset((page - 1) * page_size).limit(page_size).all()

                result_data = []
                for tx in txs:
                    inputs = session.query(AddressTransaction.address).filter_by(tx_hash=tx.hash, role='input').distinct().all()
                    outputs = session.query(AddressTransaction.address).filter_by(tx_hash=tx.hash, role='output').distinct().all()
                    result_data.append({
                        "tx_hash": tx.hash,
                        "block_hash": tx.block_hash,
                        "block_height": tx.block_height,
                        "timestamp": tx.timestamp,
                        "input_addresses": [i[0] for i in inputs],
                        "output_addresses": [o[0] for o in outputs],
                        "tx_amount": tx.tx_amount
                    })

                return {"total": total_count, "data": result_data}

        # 区块相关
        @self.app.get("/block/latest/{count}")
        async def get_latest_blocks(count: int):
            if not 1 <= count <= 50:
                raise HTTPException(status_code=400, detail="Count must be between 1 and 50.")
            with self.db.get_session() as session:
                blocks = session.query(BlockInfo).order_by(BlockInfo.height.desc()).limit(count).all()
                return [{
                    "height": b.height, "hash": b.hash, "timestamp": b.timestamp, "tx_count": b.tx_count,
                    "block_minner": b.block_minner,
                    "fee": b.total_fee,
                    "reward": {"block_reward": b.block_reward, "fee": b.total_fee, "total": b.total_reward},
                } for b in blocks]

        @self.app.get("/block/list/{start}/{count}")
        async def get_block_list(start: int, count: int):
            if not 1 <= count <= 100:
                raise HTTPException(status_code=400, detail="Count must be between 1 and 100.")
            with self.db.get_session() as session:
                query = session.query(BlockInfo).order_by(desc(BlockInfo.height))
                total = query.count()
                blocks = query.offset(start).limit(count).all()
                
                data = [{
                    "height": b.height,
                    "block_minner": b.block_minner,
                    "tx_count": b.tx_count,
                    "timestamp": b.timestamp,
                    "size": b.size,
                    "reward": {"block_reward": b.block_reward, "fee": b.total_fee, "total": b.total_reward},
                    "avg_fee_per_tx": b.total_fee / b.tx_count if b.tx_count > 0 else 0
                } for b in blocks]
                
                return {"total": total, "data": data}

        async def get_full_block_details(block: BlockInfo, session):
            """获取包含完整交易列表的区块详情"""
            tx_infos = session.query(TransactionInfo).filter_by(block_hash=block.hash).order_by(TransactionInfo.tx_index).all()
            
            txs_details = []
            for tx in tx_infos:
                inputs = session.query(AddressTransaction).filter_by(tx_hash=tx.hash, role='input').all()
                outputs = session.query(AddressTransaction).filter_by(tx_hash=tx.hash, role='output').all()
                txs_details.append({
                    "tx_hash": tx.hash,
                    "tx_in": [{"address": i.address, "amount": -i.value} for i in inputs],
                    "tx_out": [{"address": o.address, "amount": o.value} for o in outputs],
                    "fee": tx.fee,
                    "tx_amount": tx.tx_amount,
                    "op_return": decode_op_return(tx.op_return_data)
                })

            return {
                "block": {
                    "height": block.height, "hash": block.hash, "prev_hash": block.prev_hash,
                    "merkle_root": block.merkle_root, "timestamp": block.timestamp, "tx_count": block.tx_count,
                    "miner": block.block_minner, "size": block.size, "bits": block.bits, "nonce": block.nonce,
                    "block_reward": block.block_reward, "total_fee": block.total_fee,
                    "total_reward": block.total_reward, "total_tx_amount": block.total_tx_amount
                },
                "txs": txs_details
            }

        @self.app.get("/block/height/{height}")
        async def get_block_by_height(height: int):
            with self.db.get_session() as session:
                block = session.query(BlockInfo).filter_by(height=height).first()
                if not block:
                    raise HTTPException(status_code=404, detail="Block not found.")
                return await get_full_block_details(block, session)

        @self.app.get("/block/hash/{b_hash}")
        async def get_block_by_hash(b_hash: str):
            with self.db.get_session() as session:
                block = session.query(BlockInfo).filter_by(hash=b_hash).first()
                if not block:
                    raise HTTPException(status_code=404, detail="Block not found.")
                return await get_full_block_details(block, session)

        # 地址相关
        @self.app.get("/address/{address}/txs")
        async def get_transactions_by_address(address: str, page: int = 1, page_size: int = 50):
            with self.db.get_session() as session:
                # 1. 汇总信息
                balance = session.query(func.sum(AddressUTXO.value)).filter_by(address=address).scalar() or 0
                total_sent = session.query(func.sum(AddressTransaction.value)).filter_by(address=address, role='input').scalar() or 0
                total_received = session.query(func.sum(AddressTransaction.value)).filter_by(address=address, role='output').scalar() or 0

                # 2. 分页查询唯一的交易哈希
                total_txs = session.query(AddressTransaction.tx_hash).filter_by(address=address).distinct().count()
                subquery = session.query(
                    AddressTransaction.tx_hash,
                    func.max(AddressTransaction.timestamp).label('max_ts')
                ).filter_by(address=address).group_by(AddressTransaction.tx_hash).subquery()
                paginated_tx_hashes_query = session.query(subquery.c.tx_hash).order_by(desc(subquery.c.max_ts)).offset((page - 1) * page_size).limit(page_size)
                tx_hashes = [row[0] for row in paginated_tx_hashes_query.all()]

                if not tx_hashes:
                    return {
                        "result": 1, "address": address, "balance": balance,
                        "total_sent": abs(total_sent), "total_received": total_received,
                        "tx_count": total_txs, "txs": []
                    }

                # 3. 批量获取交易的详细信息
                tx_infos = {tx.hash: tx for tx in session.query(TransactionInfo).filter(TransactionInfo.hash.in_(tx_hashes)).all()}
                all_addr_txs = session.query(AddressTransaction).filter(AddressTransaction.tx_hash.in_(tx_hashes)).all()
                addr_txs_by_hash = defaultdict(list)
                for at in all_addr_txs:
                    addr_txs_by_hash[at.tx_hash].append(at)

                # 4. 构建返回数据
                txs_data = []
                for tx_hash in tx_hashes:
                    tx_info = tx_infos.get(tx_hash)
                    if not tx_info:
                        continue

                    records_for_tx = addr_txs_by_hash[tx_hash]
                    ins = [{"address": r.address, "value": -r.value} for r in records_for_tx if r.role == 'input']
                    outs = [{"address": r.address, "value": r.value} for r in records_for_tx if r.role == 'output']
                    net_value = sum(r.value for r in records_for_tx if r.address == address)
                    role = 'send' if any(r.address == address and r.role == 'input' for r in records_for_tx) else 'receive'

                    txs_data.append({
                        "tx_hash": tx_hash, "block_height": tx_info.block_height, "timestamp": tx_info.timestamp,
                        "role": role, "value": net_value, "tx_amount": tx_info.tx_amount, "fee": tx_info.fee,
                        "ins": ins, "outs": outs
                    })
                
                return {
                    "result": 1, "address": address, "balance": balance,
                    "total_sent": abs(total_sent), "total_received": total_received,
                    "tx_count": total_txs, "txs": txs_data
                }

        @self.app.get("/address/{address}/balance")
        async def get_balance_by_address(address: str):
            with self.db.get_session() as session:
                balance = session.query(func.sum(AddressUTXO.value)).filter_by(address=address).scalar() or 0
                return {"address": address, "balance": balance, "unit": "tinyalt"}

        @self.app.get("/address/{address}/utxos")
        async def get_utxos_by_address(address: str):
            # 获取mempool中已花费的UTXO，以避免返回它们
            mempool_spent_utxos = self.mempool.spent_utxos
            
            with self.db.get_session() as session:
                try:
                    utxos_from_db = session.query(AddressUTXO).filter_by(address=address).all()
                    
                    # 过滤掉在mempool中已被花费的UTXO
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
                except Exception as e:
                    log.error(f"Error querying UTXOs for address {address}: {e}", exc_info=True)
                    raise HTTPException(status_code=500, detail="Internal server error")
        
        # Mempool 相关
        @self.app.get("/mempool/info")
        async def get_mempool_info():
            # 这个接口现在可以更准确地反映mempool的状态
            txs = self.mempool.transactions
            result = []
            for tx_hash, tx in txs.items():
                # 使用mempool的辅助函数来计算费用，更可靠
                fee = self.mempool.calculate_fee(tx)
                if fee == -1: # 表示UTXO信息不完整，可能chain_state还没同步
                    continue

                input_amount = sum(self.blockchain.chain_state.get_utxo(tx_in).value for tx_in in tx.tx_ins)
                output_amount = sum(tx_out.value for tx_out in tx.tx_outs)
                
                input_addresses = [self.blockchain.chain_state.get_utxo(tx_in).locking_script.decode('utf-8', 'ignore') for tx_in in tx.tx_ins]
                output_addresses = [tx_out.locking_script.decode('utf-8', 'ignore') for tx_out in tx.tx_outs]

                result.append({
                    "tx_hash": tx_hash.hex(),
                    "input_amount": input_amount,
                    "output_amount": output_amount,
                    "fee": fee,
                    "input_addresses": list(set(input_addresses)),
                    "output_addresses": output_addresses
                })
            return {"count": len(result), "transactions": result}

    async def run(self):
        config = uvicorn.Config(self.app, host="0.0.0.0", port=self.port, log_level="info")
        server = uvicorn.Server(config)
        log.info(f"RPC server started on http://0.0.0.0:{self.port}")
        await server.serve()
