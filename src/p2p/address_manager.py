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
    host = Column(TEXT, nullable=True)
    port = Column(Integer, nullable=True)

    # 状态 (可变)
    last_seen = Column(Integer, default=0, index=True) # 上次成功
    last_attempt = Column(Integer, default=0) # 上次尝试
    failed_attempts = Column(Integer, default=0)
    score = Column(Integer, default=0, index=True)  # 节点质量评分

    def to_dict(self):
        return {
            "node_id": self.node_id,
            "host": self.host,
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
    def __init__(self, db_wrapper: SQLAlchemyWrapper, seed_nodes, active_peers_getter):
        self.db = db_wrapper
        # PeerManager.get_active_node_ids() 的回调
        self.get_active_node_ids = active_peers_getter
        # 确保表已创建
        self.db.create_all_tables()
        self.seed_nodes = seed_nodes
        self.init_seeds_node()
        log.info(f"AddressManager 已初始化, 数据库: {db_wrapper.engine.url}")

    def _get_session(self) -> Session:
        return self.db.get_session()

    def init_seeds_node(self):
        # 把种子节点增加到数据
        self.add_peers_from_list(self.seed_nodes)
    def get_all_peers(self):
        with self._get_session() as session:
            return [ item.to_dict() for item in  session.query(KnownPeer).all()]

    def get_peers_to_try(self, limit: int, exclude_ids: set = None) -> list[dict]:
        """
        从数据库获取“好”节点列表，用于启动时或需要更多连接时。
        """
        if exclude_ids is None:
            exclude_ids = set()

        with self._get_session() as session:
            try:
                # 策略：选择分数高、且最近5分钟内未失败过的节点
                now = int(time.time())
                five_minutes_ago = now - 300 # 5分钟内不要重试失败的

                query = session.query(KnownPeer).filter(
                    KnownPeer.last_attempt < five_minutes_ago,
                    KnownPeer.node_id.notin_(exclude_ids)
                ).order_by(KnownPeer.score.desc(), KnownPeer.last_seen.desc()).limit(limit)

                peers = [peer.to_dict() for peer in query.all() if peer.host]
                return peers
            except Exception as e:
                log.debug("Exception details for get_peers_to_try:", exc_info=True)
                log.error(f"AddressManager DB error (get_peers_to_try): {e}")
                session.rollback()
                return []

    def update_peer_score(self, node_id: str, score_change: int,
                          is_success: bool = False, ip: str = None, port: int = None):
        """
        (核心) 更新节点分数和状态的统一方法。
        """
        now = int(time.time())
        with self._get_session() as session:
            try:
                peer = session.query(KnownPeer).filter(KnownPeer.node_id == node_id).first()
                if not peer:
                    # 如果节点不存在 (例如，通过广播新发现的)，则创建一个
                    if is_success:
                        peer_data = {
                            "node_id": node_id, "host": ip, "port": port,
                            "last_seen": now, "last_attempt": now, "failed_attempts": 0,
                            "score": 10  # 初始分数
                        }
                        session.merge(KnownPeer(**peer_data))
                        log.debug(f"AddrMan: Created and marked success for new peer {node_id}")
                    # 如果不是成功事件，且节点不存在，则无需操作
                    return

                # 更新分数
                peer.score += score_change
                log.debug(f"AddrMan: Updated score for {node_id}, change: {score_change}, new_score: {peer.score}")

                # 更新状态
                peer.last_attempt = now
                if is_success:
                    peer.last_seen = now
                    peer.failed_attempts = 0
                    if ip and port:
                        peer.host = ip
                        peer.port = port
                else:
                    peer.failed_attempts += 1

                session.commit()
            except Exception as e:
                log.debug("Exception details for update_peer_score:", exc_info=True)
                log.error(f"AddressManager DB error (update_peer_score): {e}")
                session.rollback()

    def mark_peer_success(self, node_id: str, ip: str, port: int):
        """(重要) 当握手成功时调用此方法。"""
        self.update_peer_score(node_id, 10, is_success=True, ip=ip, port=port)

    def mark_peer_failed(self, node_id: str):
        """当连接尝试失败时调用此方法。"""
        self.update_peer_score(node_id, -10)

    def mark_peer_disconnected(self, node_id: str):
        """当连接断开时调用此方法。"""
        self.update_peer_score(node_id, -5)

    def add_peers_from_list(self, peer_list: list[dict]):
        """
        (重要) 由 handle_addr (PULL) 和 handle_notify_new_peer (PUSH) 调用。
        新逻辑：
        - 忽略已连接的节点。
        - 如果 node_id 已知，更新地址。
        - 如果是新节点，添加并给予初始分数。
        """
        active_node_ids = self.get_active_node_ids()
        with self._get_session() as session:
            try:
                for peer_info in peer_list:
                    node_id = peer_info.get('node_id')
                    host = peer_info.get('host')
                    port = peer_info.get('port')

                    if not node_id or not host or not port:
                        continue
                    if node_id in active_node_ids:
                        continue # 忽略已连接的节点

                    # 检查数据库中是否已存在
                    peer = session.query(KnownPeer).filter(KnownPeer.node_id == node_id).first()
                    if peer:
                        # 已知节点：更新地址
                        peer.host = host
                        peer.port = port
                    else:
                        # 新节点：添加并给予初始分数
                        new_peer = KnownPeer(
                            node_id=node_id, host=host, port=port,
                            score=5 # 初始分数
                        )
                        session.add(new_peer)
                session.commit()
            except Exception as e:
                log.debug("Exception details for add_peers_from_list:", exc_info=True)
                log.warning(f"AddressManager DB warning (add_peers_from_list): {e}")
                session.rollback()

    def cull_bad_peers(self):
        """
        移除分数过低的节点。
        """
        with self._get_session() as session:
            try:
                # 删除分数低于 -50 的节点
                deleted_count = session.query(KnownPeer).filter(KnownPeer.score < -50).delete()
                if deleted_count > 0:
                    session.commit()
                    log.info(f"AddrMan: Culled {deleted_count} bad peers from DB.")
            except Exception as e:
                log.debug("Exception details for cull_bad_peers:", exc_info=True)
                log.error(f"AddressManager DB error (cull_bad_peers): {e}")
                session.rollback()
