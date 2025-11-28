import unittest
import tempfile
import os
from unittest.mock import Mock, patch, MagicMock
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.p2p.address_manager import AddressManager, KnownPeer
from src.storage.sql_alchemy_wrapper import SQLAlchemyWrapper


class TestAddressManager(unittest.TestCase):
    def setUp(self):
        # 创建临时数据库文件
        self.temp_db = tempfile.NamedTemporaryFile(delete=False, suffix='.db')
        self.temp_db.close()
        
        # 初始化数据库
        self.db_wrapper = SQLAlchemyWrapper(self.temp_db.name)
        # 确保KnownPeer模型被包含在Base中
        from src.p2p.address_manager import KnownPeer
        KnownPeer.metadata.create_all(self.db_wrapper.engine)
        
        # 创建模拟的种子节点和活跃节点获取器
        self.seed_nodes = [
            {"node_id": "node1", "host": "192.168.1.1", "port": 8001},
            {"node_id": "node2", "host": "192.168.1.2", "port": 8002}
        ]
        self.active_peers_getter = Mock(return_value=set())
        
        # 创建 AddressManager 实例
        self.address_manager = AddressManager(
            self.db_wrapper, 
            self.seed_nodes, 
            self.active_peers_getter
        )


    def tearDown(self):
        # 清理临时文件
        os.unlink(self.temp_db.name)

    def test_init_seeds_node(self):
        """测试初始化种子节点"""
        # 验证种子节点被正确添加
        peers = self.address_manager.get_all_peers()
        self.assertEqual(len(peers), 2)
        
        peer_ids = {peer['node_id'] for peer in peers}
        self.assertIn('node1', peer_ids)
        self.assertIn('node2', peer_ids)

    def test_add_peers_from_list(self):
        """测试添加节点列表"""
        new_peers = [
            {"node_id": "node3", "host": "192.168.1.3", "port": 8003},
            {"node_id": "node4", "host": "192.168.1.4", "port": 8004}
        ]
        
        self.address_manager.add_peers_from_list(new_peers)
        
        peers = self.address_manager.get_all_peers()
        self.assertEqual(len(peers), 4)  # 2个种子节点 + 2个新节点
        
        peer_dict = {peer['node_id']: peer for peer in peers}
        self.assertIn('node3', peer_dict)
        self.assertIn('node4', peer_dict)
        self.assertEqual(peer_dict['node3']['host'], '192.168.1.3')
        self.assertEqual(peer_dict['node4']['port'], 8004)

    def test_add_peers_from_list_with_active_peer(self):
        """测试添加节点列表时忽略已连接节点"""
        # 设置活跃节点包含node3
        self.active_peers_getter.return_value = {'node3'}
        
        new_peers = [
            {"node_id": "node3", "host": "192.168.1.3", "port": 8003},  # 应该被忽略
            {"node_id": "node4", "host": "192.168.1.4", "port": 8004}   # 应该被添加
        ]
        
        self.address_manager.add_peers_from_list(new_peers)
        
        peers = self.address_manager.get_all_peers()
        self.assertEqual(len(peers), 3)  # 2个种子节点 + 1个新节点(node4)
        
        peer_ids = {peer['node_id'] for peer in peers}
        self.assertNotIn('node3', peer_ids)
        self.assertIn('node4', peer_ids)

    def test_update_peer_score_new_peer(self):
        """测试更新新节点分数"""
        # 添加一个新节点
        self.address_manager.update_peer_score(
            "node5", 10, is_success=True, ip="192.168.1.5", port=8005
        )
        
        peers = self.address_manager.get_all_peers()
        # self.assertEqual(len(peers), 3)  # 2个种子节点 + 1个新节点
        print(peers)
        peer_dict = {peer['node_id']: peer for peer in peers}
        self.assertIn('node5', peer_dict)
        self.assertEqual(peer_dict['node5']['host'], '192.168.1.5')
        self.assertEqual(peer_dict['node5']['port'], 8005)

    def test_update_peer_score_existing_peer(self):
        """测试更新现有节点分数"""
        # 先添加一个节点
        new_peer = [{"node_id": "node3", "host": "192.168.1.3", "port": 8003}]
        self.address_manager.add_peers_from_list(new_peer)
        
        # 更新该节点分数
        self.address_manager.update_peer_score("node3", 20)
        
        # 验证分数更新
        with self.address_manager._get_session() as session:
            peer = session.query(KnownPeer).filter(KnownPeer.node_id == "node3").first()
            self.assertEqual(peer.score, 25)  # 初始分数5 + 20

    def test_mark_peer_success(self):
        """测试标记节点连接成功"""
        # 添加一个节点
        new_peer = [{"node_id": "node3", "host": "192.168.1.3", "port": 8003}]
        self.address_manager.add_peers_from_list(new_peer)
        
        # 标记连接成功
        self.address_manager.mark_peer_success("node3", "192.168.1.3", 8003)
        
        # 验证状态更新
        with self.address_manager._get_session() as session:
            peer = session.query(KnownPeer).filter(KnownPeer.node_id == "node3").first()
            self.assertEqual(peer.score, 15)  # 初始分数5 + 10
            self.assertEqual(peer.failed_attempts, 0)

    def test_mark_peer_failed(self):
        """测试标记节点连接失败"""
        # 添加一个节点
        new_peer = [{"node_id": "node3", "host": "192.168.1.3", "port": 8003}]
        self.address_manager.add_peers_from_list(new_peer)
        
        # 标记连接失败
        self.address_manager.mark_peer_failed("node3")
        
        # 验证状态更新
        with self.address_manager._get_session() as session:
            peer = session.query(KnownPeer).filter(KnownPeer.node_id == "node3").first()
            self.assertEqual(peer.score, -5)  # 初始分数5 - 10
            self.assertEqual(peer.failed_attempts, 1)

    def test_get_peers_to_try(self):
        """测试获取待连接节点列表"""
        # 添加更多节点
        new_peers = [
            {"node_id": "node3", "host": "192.168.1.3", "port": 8003},
            {"node_id": "node4", "host": "192.168.1.4", "port": 8004}
        ]
        self.address_manager.add_peers_from_list(new_peers)
        
        # 更新节点分数以创建排序
        self.address_manager.update_peer_score("node3", 20)  # 高分节点
        self.address_manager.update_peer_score("node4", -20)  # 低分节点
        
        # 手动修改last_attempt字段，使其满足过滤条件
        with self.address_manager._get_session() as session:
            node3 = session.query(KnownPeer).filter(KnownPeer.node_id == "node3").first()
            node4 = session.query(KnownPeer).filter(KnownPeer.node_id == "node4").first()
            # 将last_attempt设置为很久以前，以通过过滤条件
            node3.last_attempt = 0
            node4.last_attempt = 0
            session.commit()
        
        # 获取待连接节点
        peers_to_try = self.address_manager.get_peers_to_try(3)
        
        # 验证返回结果
        self.assertEqual(len(peers_to_try), 3)
        # 验证按分数排序（高分在前）
        self.assertEqual(peers_to_try[0]['node_id'], 'node3')

    def test_cull_bad_peers(self):
        """测试清理低分节点"""
        # 添加节点并降低其中一个节点的分数
        new_peers = [
            {"node_id": "node3", "host": "192.168.1.3", "port": 8003},
            {"node_id": "node4", "host": "192.168.1.4", "port": 8004}
        ]
        self.address_manager.add_peers_from_list(new_peers)
        
        # 将node4的分数降低到-60
        with self.address_manager._get_session() as session:
            peer = session.query(KnownPeer).filter(KnownPeer.node_id == "node4").first()
            peer.score = -60
            session.commit()
        
        # 清理低分节点
        self.address_manager.cull_bad_peers()
        
        # 验证低分节点被删除
        peers = self.address_manager.get_all_peers()
        self.assertEqual(len(peers), 3)  # 2个种子节点 + 1个正常节点(node3)
        
        peer_ids = {peer['node_id'] for peer in peers}
        self.assertIn('node1', peer_ids)  # 种子节点
        self.assertIn('node2', peer_ids)  # 种子节点
        self.assertIn('node3', peer_ids)  # 正常节点
        self.assertNotIn('node4', peer_ids)  # 被删除的低分节点


if __name__ == '__main__':
    unittest.main()