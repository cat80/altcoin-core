import logging
import threading
from typing import List
from sqlalchemy.orm import Session
from sqlalchemy import text, String, desc
import asyncio
from core.blockchain import Blockchain
from p2p.event_bus import EventBus
from storage.sql_alchemy_wrapper import SQLAlchemyWrapper
from indexer.model import Base, IndexerState, AddressUTXO, BlockInfo, TransactionInfo, AddressTransaction

log = logging.getLogger(__name__)

class BlockIndexer:
    """
    区块索引器 (同步版本)。
    """

    def __init__(self, db_wrapper: SQLAlchemyWrapper, blockchain: Blockchain,event_bus:EventBus=None):
        self.db = db_wrapper
        self.blockchain = blockchain
        self.db.create_all_tables(Base)
        log.info("BlockIndexer (同步) 已初始化。")
        self.event_bus = event_bus
        if self.event_bus:
            self.event_bus.subscribe("block_validated",self.on_block_validate)
        self.is_sync_event = threading.Event()

    def _get_session(self) -> Session:
        return self.db.get_session()

    async def on_block_validate(self,block):
        log.debug('收到区块确认，开始重建索引...')
        if not self.is_sync_event.is_set():
            await asyncio.to_thread(self.sync_to_chain)
        else:
            log.debug('索引正在重建中，等待下次重建')

    def sync_to_chain(self):
        """
        确保索引器数据库与区块链数据同步，包含重组处理。
        """

        if self.is_sync_event.is_set():
            log.debug('索引器正在重建放弃本次重建...')
            return
        try:
            self.is_sync_event.set()
            log.info("开始检查索引器与区块链的一致性...")
            while True:
                with self._get_session() as session:
                    last_indexed_height_record = session.query(IndexerState).filter_by(key='last_indexed_height').first()
                    last_indexed_height = int(last_indexed_height_record.value) if last_indexed_height_record else -1

                chain_tip_info = self.blockchain.get_best_tip()
                if not chain_tip_info:
                    log.info("区块链为空，无需同步。")
                    return

                chain_height = chain_tip_info['height']
                log.info(f"索引器高度: {last_indexed_height}, 区块链高度: {chain_height}")
                if chain_height == last_indexed_height:
                    log.debug('索引器高度和区块高度一致，已经是最新不需要同步')
                    return
                if last_indexed_height < chain_height:
                    log.info(f"索引器落后，开始从区块 {last_indexed_height + 1} 同步...")

                    if last_indexed_height > -1:
                        indexed_block_info = self._get_indexed_block_info(last_indexed_height)
                        real_header_info = self.blockchain.block_index.get_header_by_height(last_indexed_height)

                        if not indexed_block_info or indexed_block_info.hash != real_header_info['block_hash'].hex():
                            log.warning(f"检测到链在高度 {last_indexed_height} 发生分叉！开始回滚索引器。")
                            self._rollback_to_common_ancestor()
                            continue

                    for height in range(last_indexed_height + 1, chain_height + 1):
                        header_info = self.blockchain.block_index.get_header_by_height(height)
                        if header_info:
                            self._process_block(header_info)
                        else:
                            log.error(f"同步失败：在 block_index 中找不到高度为 {height} 的区块。")
                            break

                    log.info("索引器与区块链一致性检查完成。")
                    break
        except Exception as e:
            log.debug(f'索引失败:{e}',exc_info=True)
            log.error(f'索引失败,{e}')
        finally:
            self.is_sync_event.clear()

    def _rollback_to_common_ancestor(self):
        """从索引器最高处开始，逐块回滚，直到与主链一致。"""
        with self._get_session() as session:
            while True:
                last_block = session.query(BlockInfo).order_by(desc(BlockInfo.height)).first()
                if not last_block:
                    log.info("索引器已完全回滚。")
                    break

                height = last_block.height
                real_header = self.blockchain.block_index.get_header_by_height(height)

                if real_header and last_block.hash == real_header['block_hash'].hex():
                    log.info(f"找到共同祖先，高度: {height}，哈希: {last_block.hash}")
                    state = session.query(IndexerState).filter_by(key='last_indexed_height').one()
                    state.value = str(height)
                    session.commit()
                    break

                log.info(f"回滚索引器区块，高度: {height}")
                self._delete_block_data(height, session)
                session.commit()

    def _get_indexed_block_info(self, height: int) -> BlockInfo | None:
        with self._get_session() as session:
            return session.query(BlockInfo).filter_by(height=height).one_or_none()

    def _delete_block_data(self, height: int, session: Session):
        """删除指定高度的所有索引数据。"""
        session.query(AddressUTXO).filter_by(block_height=height).delete(synchronize_session=False)
        session.query(BlockInfo).filter_by(height=height).delete(synchronize_session=False)
        session.query(TransactionInfo).filter_by(block_height=height).delete(synchronize_session=False)
        session.query(AddressTransaction).filter_by(block_height=height).delete(synchronize_session=False)


    def _process_block(self, block_header: dict, existing_session: Session = None):
        block_height = block_header['height']
        block = self.blockchain.block_storage.read_block(block_header['file_index'], block_header['file_offset'])
        if not block:
            log.error(f"索引器无法读取区块 {block_header['block_hash'].hex()}，跳过。")
            return
        block_time = block.header.timestamp
        log.debug(f"索引器开始处理区块 {block_height}...")

        def process_in_session(session: Session):
            # --- 阶段一: 收集区块内的基本信息 ---
            spent_in_this_block_keys = set()
            new_outputs_in_this_block = {}  # {(tx_hash, index): (address, value)}

            for tx in block.transactions:
                tx_hash_hex = tx.hash().hex()
                # 收集新输出
                for i, tx_out in enumerate(tx.tx_outs):
                    address = tx_out.locking_script.decode('utf-8', 'ignore')
                    new_outputs_in_this_block[(tx_hash_hex, i)] = (address, tx_out.value)

                # 收集被花费的输入引用
                if not tx.is_coinbase():
                    for tx_in in tx.tx_ins:
                        spent_in_this_block_keys.add(f"{tx_in.prev_tx_hash.hex()}:{tx_in.prev_tx_out_index}")

            # --- 阶段二: 获取详情并执行数据库I/O ---

            # 1. 获取所有被花费UTXO的详细信息
            spent_utxo_details = {}  # {(tx_hash, index): (address, value)}

            # 1a. **先查询** 数据库中存在的 (即块外) UTXO的详情
            if spent_in_this_block_keys:
                utxos_to_delete = session.query(AddressUTXO).filter(
                    (AddressUTXO.tx_hash + ':' + AddressUTXO.output_index.cast(String)).in_(spent_in_this_block_keys)
                ).all()
                for utxo in utxos_to_delete:
                    spent_utxo_details[(utxo.tx_hash, utxo.output_index)] = (utxo.address, utxo.value)

                # 1b. **然后删除** 这些UTXO
                for utxo in utxos_to_delete:
                    session.delete(utxo)

            # 1c. 补充本区块内创建并花费的UTXO的详情
            for key_str in spent_in_this_block_keys:
                txh, idx_str = key_str.split(':')
                idx = int(idx_str)
                key = (txh, idx)
                if key in new_outputs_in_this_block and key not in spent_utxo_details:
                    spent_utxo_details[key] = new_outputs_in_this_block[key]

            # 2. 添加真正未被花费的新UTXO
            for (tx_hash, out_idx), (addr, val) in new_outputs_in_this_block.items():
                if f"{tx_hash}:{out_idx}" not in spent_in_this_block_keys:
                    session.add(AddressUTXO(
                        tx_hash=tx_hash, output_index=out_idx, address=addr,
                        value=val, block_height=block_height
                    ))

            # --- 阶段三: 索引交易和地址关系 (会计) ---
            block_reward, total_fee, total_tx_amount = 0, 0, 0
            block_minner = ''

            for tx_index, tx in enumerate(block.transactions):
                tx_hash_hex = tx.hash().hex()
                input_amount, output_amount = 0, 0
                input_addresses = set()

                # 处理输入 (支出) - 现在 spent_utxo_details 是完整的
                if not tx.is_coinbase():
                    for tx_in in tx.tx_ins:
                        key = (tx_in.prev_tx_hash.hex(), tx_in.prev_tx_out_index)
                        if key in spent_utxo_details:
                            address, value = spent_utxo_details[key]
                            input_amount += value
                            input_addresses.add(address)
                            session.add(AddressTransaction(
                                timestamp=block_time, address=address, tx_hash=tx_hash_hex,
                                block_height=block_height, role='input', value=-value,
                                prev_tx_hash=tx_in.prev_tx_hash.hex(),
                                prev_tx_out_index=tx_in.prev_tx_out_index
                            ))

                # 处理输出 (收入)
                change_amount = 0
                for i, tx_out in enumerate(tx.tx_outs):
                    output_amount += tx_out.value
                    address = tx_out.locking_script.decode('utf-8', 'ignore')
                    session.add(AddressTransaction(
                        address=address, tx_hash=tx_hash_hex, block_height=block_height,
                        role='output', value=tx_out.value, timestamp=block_time
                    ))
                    if address in input_addresses:
                        change_amount += tx_out.value

                # 计算交易字段
                fee, tx_amount = 0, 0
                if tx.is_coinbase():
                    block_reward = output_amount
                    block_minner = tx.tx_outs[0].locking_script.decode('utf-8', 'ignore') if tx.tx_outs else ''
                else:
                    fee = input_amount - output_amount
                    tx_amount = input_amount - change_amount
                    total_fee += fee
                    total_tx_amount += tx_amount

                session.add(TransactionInfo(
                    hash=tx_hash_hex, block_hash=block.hash().hex(), block_height=block_height,
                    timestamp=block.header.timestamp, tx_index=tx_index, fee=fee,
                    input_amount=input_amount, output_amount=output_amount, tx_amount=tx_amount,
                    input_count=len(tx.tx_ins), output_count=len(tx.tx_outs), op_return_data=None
                ))

            # 索引区块信息
            total_reward = block_reward
            block_reward = block_reward - total_fee
            session.add(BlockInfo(
                height=block_height, hash=block.hash().hex(), prev_hash=block.header.prev_block_hash.hex(),
                merkle_root=block.header.merkle_root.hex(), timestamp=block.header.timestamp,
                block_minner=block_minner, tx_count=len(block.transactions), size=block.get_size(),
                bits=block.header.bits, nonce=block.header.nonce, block_reward=block_reward,
                total_fee=total_fee, total_reward=total_reward, total_tx_amount=total_tx_amount
            ))

            # 更新索引器状态
            state = session.query(IndexerState).filter_by(key='last_indexed_height').first()
            if state:
                state.value = str(block_height)
            else:
                session.add(IndexerState(key='last_indexed_height', value=str(block_height)))

        # --- 函数体 ---
        if existing_session:
            process_in_session(existing_session)
        else:
            with self._get_session() as session:
                try:
                    process_in_session(session)
                    session.commit()
                    log.info(f"区块 {block_height} 索引完成。")
                except Exception as e:
                    log.error(f"索引区块 {block_height} 时发生错误: {e}", exc_info=True)
                    session.rollback()
                    raise