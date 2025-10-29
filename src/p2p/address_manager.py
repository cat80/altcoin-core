import time
import logging
from sqlalchemy import Column, Integer, TEXT
from sqlalchemy.orm import Session
from storage.sql_alchemy_wrapper import SQLAlchemyWrapper, Base

log = logging.getLogger(__name__)

# ==========================================================
# 1. 数据模型 (Data Model)
# ==========================================================
class KnownPeer(Base):
    """
    AddressManager 的 SQLAlchemy 数据模型。
    使用 node_id 作为主键，以解决 IP 变化的问题。
    """
    __tablename__ = 'known_peers'

    # 身份
    node_id = Column(TEXT, primary_key=True)

    # 位置 (可变)
    ip = Column(TEXT, nullable=True)
    port = Column(Integer, nullable=True)

    # 状态 (可变)
    last_seen = Column(Integer, default=0, index=True) # 上次成功
    last_attempt = Column(Integer, default=0) # 上次尝试
    failed_attempts = Column(Integer, default=0)

    def to_dict(self):
        return {
            "node_id": self.node_id,
            "ip": self.ip,
            "port": self.port
        }

# ==========================================================
# 2. 逻辑封装 (AddressManager)
# ==========================================================
class AddressManager:
    """
    管理所有已知节点的持久化存储 (SQLite)。
    注意：所有数据库操作都是同步的。
    """
    def __init__(self, db_wrapper: SQLAlchemyWrapper):
        self.db = db_wrapper
        # 确保表已创建
        self.db.create_all_tables()
        log.info(f"AddressManager 已初始化, 数据库: {db_wrapper.engine.url}")

    def _get_session(self) -> Session:
        return self.db.get_session()

    def get_peers_to_try(self, limit: int, exclude_ids: set = None) -> list[dict]:
        """
        从数据库获取“好”节点列表，用于启动时连接。
        """
        if exclude_ids is None:
            exclude_ids = set()

        with self._get_session() as session:
            try:
                # 策略：选择失败次数少、最近未尝试过的节点
                now = int(time.time())
                one_hour_ago = now - 3600 # 1小时内不要重试失败的

                query = session.query(KnownPeer).filter(
                    KnownPeer.failed_attempts < 5,
                    KnownPeer.last_attempt < one_hour_ago,
                    KnownPeer.node_id.notin_(exclude_ids)
                ).order_by(KnownPeer.last_seen.desc()).limit(limit)

                peers = [peer.to_dict() for peer in query.all() if peer.ip]
                return peers
            except Exception as e:
                log.error(f"AddressManager DB error (get_peers_to_try): {e}")
                session.rollback()
                return []

    def mark_peer_success(self, node_id: str, ip: str, port: int):
        """
        (重要) 当握手成功时调用此方法。
        使用 UPSERT (merge) 逻辑更新或插入节点信息。
        """
        now = int(time.time())
        peer_data = {
            "node_id": node_id,
            "ip": ip,
            "port": port,
            "last_seen": now,
            "last_attempt": now,
            "failed_attempts": 0 # (关键) 成功后清零
        }

        with self._get_session() as session:
            try:
                # session.merge() 是 SQLAlchemy 的 UPSERT
                session.merge(KnownPeer(**peer_data))
                session.commit()
                log.debug(f"AddrMan: Marked peer success (UPSERT): {node_id}")
            except Exception as e:
                log.error(f"AddressManager DB error (mark_peer_success): {e}")
                session.rollback()

    def mark_peer_failed(self, node_id: str):
        """
        当连接尝试失败时调用此方法。
        """
        now = int(time.time())
        with self._get_session() as session:
            try:
                peer = session.query(KnownPeer).filter(KnownPeer.node_id == node_id).first()
                if peer:
                    peer.last_attempt = now
                    peer.failed_attempts += 1
                    session.commit()
                    log.debug(f"AddrMan: Marked peer failed: {node_id}, attempts={peer.failed_attempts}")
            except Exception as e:
                log.error(f"AddressManager DB error (mark_peer_failed): {e}")
                session.rollback()

    def add_peers_from_list(self, peer_list: list[dict]):
        """
        (重要) 由 handle_addr (PULL) 和 handle_notify_new_peer (PUSH) 调用。
        批量添加新地址，但“仅在不存在时” (ON CONFLICT DO NOTHING)。
        """
        with self._get_session() as session:
            try:
                new_peers_added = 0
                for peer_info in peer_list:
                    node_id = peer_info.get('node_id')
                    ip = peer_info.get('ip')
                    port = peer_info.get('port')

                    if not node_id or not ip or not port:
                        continue # 忽略无效数据

                    # 检查是否已存在
                    exists = session.query(KnownPeer.node_id).filter_by(node_id=node_id).first() is not None
                    if not exists:
                        # 只添加新节点，不更新旧节点 (这是拉取逻辑)
                        new_peer = KnownPeer(
                            node_id=node_id,
                            ip=ip,
                            port=port,
                            last_attempt=0,
                            last_seen=0, # 尚未亲身验证
                            failed_attempts=0
                        )
                        session.add(new_peer)
                        new_peers_added += 1

                if new_peers_added > 0:
                    session.commit()
                    log.debug(f"AddrMan: Added {new_peers_added} new peers to DB from list.")

            except Exception as e:
                log.warning(f"AddressManager DB warning (add_peers_from_list): {e}")
                session.rollback()
