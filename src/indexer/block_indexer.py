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
        self.is_sync_event.set()
        try:
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

    def on_reorg(self, old_blocks_info: List[dict], new_blocks_info: List[dict]):
        log.info(f"索引器检测到重组：回滚 {len(old_blocks_info)} 个区块，应用 {len(new_blocks_info)} 个区块。")
        with self._get_session() as session:
            try:
                for block_info in reversed(old_blocks_info):
                    self._delete_block_data(block_info['height'], session)
                for block_info in new_blocks_info:
                    self._process_block(block_info, session)
                session.commit()
                log.info("索引器重组处理完成。")
            except Exception as e:
                log.error(f"索引器处理重组时出错: {e}", exc_info=True)
                session.rollback()

    def on_block_validated(self, block_header: dict):
        with self._get_session() as session:
            last_indexed_height_record = session.query(IndexerState).filter_by(key='last_indexed_height').first()
            last_indexed_height = int(last_indexed_height_record.value) if last_indexed_height_record else -1
        
        if block_header['height'] == last_indexed_height + 1:
             self._process_block(block_header)
        elif block_header['height'] <= last_indexed_height:
             log.debug(f"索引器已处理过区块 {block_header['height']}，跳过。")
        else:
             log.warning(f"索引器收到跳跃区块 {block_header['height']}，但当前高度为 {last_indexed_height}。将由 sync_to_chain 处理。")

    def _process_block(self, block_header: dict, existing_session: Session = None):
        # 修复：将 block_height 的定义移到顶层作用域
        block_height = block_header['height']
        
        block = self.blockchain.block_storage.read_block(block_header['file_index'], block_header['file_offset'])
        if not block:
            log.error(f"索引器无法读取区块 {block_header['block_hash'].hex()}，跳过。")
            return

        log.info(f"索引器开始处理区块 {block_height}...")

        def process_in_session(session: Session):
            # 1. 找到并删除被花费的 UTXO，同时缓存其信息
            spent_utxo_details = {} # {(tx_hash, index): (address, value)}
            spent_utxo_keys = set()
            for tx in block.transactions:
                if not tx.is_coinbase():
                    for tx_in in tx.tx_ins:
                        spent_utxo_keys.add(f"{tx_in.prev_tx_hash.hex()}:{tx_in.prev_tx_out_index}")
            
            if spent_utxo_keys:
                utxos_to_delete = session.query(AddressUTXO).filter(
                    (AddressUTXO.tx_hash + ':' + AddressUTXO.output_index.cast(String)).in_(spent_utxo_keys)
                ).all()
                for utxo in utxos_to_delete:
                    spent_utxo_details[(utxo.tx_hash, utxo.output_index)] = (utxo.address, utxo.value)
                    session.delete(utxo)

            # 2. 索引区块信息
            session.add(BlockInfo(
                height=block_height, hash=block.hash().hex(), prev_hash=block.header.prev_block_hash.hex(),
                merkle_root=block.header.merkle_root.hex(), timestamp=block.header.timestamp, tx_count=len(block.transactions)
            ))

            # 3. 索引交易、UTXO 和地址-交易关系
            for tx in block.transactions:
                tx_hash_hex = tx.hash().hex()
                session.add(TransactionInfo(
                    tx_hash=tx_hash_hex, block_hash=block.hash().hex(), block_height=block_height,
                    fee=0, timestamp=block.header.timestamp
                ))
                # 处理输出 (收入)
                for i, tx_out in enumerate(tx.tx_outs):
                    address = tx_out.locking_script.decode('utf-8', 'ignore')
                    session.add(AddressUTXO(
                        tx_hash=tx_hash_hex, output_index=i, address=address,
                        value=tx_out.value, block_height=block_height
                    ))
                    session.add(AddressTransaction(
                        address=address, tx_hash=tx_hash_hex, block_height=block_height, role='output', value=tx_out.value
                    ))
                # 处理输入 (支出)
                if not tx.is_coinbase():
                    for tx_in in tx.tx_ins:
                        key = (tx_in.prev_tx_hash.hex(), tx_in.prev_tx_out_index)
                        if key in spent_utxo_details:
                            address, value = spent_utxo_details[key]
                            session.add(AddressTransaction(
                                address=address, tx_hash=tx_hash_hex, block_height=block_height, role='input', value=-value
                            ))

            # 4. 更新索引器状态
            state = session.query(IndexerState).filter_by(key='last_indexed_height').first()
            if state:
                state.value = str(block_height)
            else:
                session.add(IndexerState(key='last_indexed_height', value=str(block_height)))

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
