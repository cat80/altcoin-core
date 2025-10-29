import asyncio
import logging
import os

from core.blockchain import Blockchain
from p2p.event_bus import EventBus
from p2p.node import P2PNode
from p2p.peer_manager import PeerManager
from p2p.protocol_handler import ProtocolHandler
from consensus.miner import Miner
from mempool.mempool import Mempool
from config import setup_logging, load_app_config
from bootstrap import setup_node
from storage.sql_alchemy_wrapper import SQLAlchemyWrapper
from p2p.address_manager import AddressManager

log = logging.getLogger(__name__)

async def main():
    # 第一步：加载日志和应用配置
    setup_logging()
    app_config = load_app_config()
    log.debug(f'原始应用配置: {app_config}')

    # 第二步：初始化节点环境（目录、锁、密钥）
    my_node_id, app_config = setup_node(app_config)
    
    # 从最终配置中获取参数
    data_dir = app_config['p2p']['data_dir']
    listen_port = app_config['p2p']['listen_port']
    my_coinbase_address = app_config['p2p']['coinbase_address']

    # 第三步：实例化所有核心组件
    event_bus = EventBus()

    # 初始化两个独立的数据库
    # 1. 区块链数据库
    blockchain = Blockchain.new_from_data_dir(data_dir)

    # 2. 地址数据库
    addr_db_path = os.path.join(data_dir, 'addr_man.db')
    addr_db_wrapper = SQLAlchemyWrapper(addr_db_path)
    address_manager = AddressManager(addr_db_wrapper)

    mempool = Mempool(event_bus)
    
    # 注入依赖
    peer_manager = PeerManager(event_bus, my_node_id, listen_port)

    # 向 ProtocolHandler 注入 AddressManager
    protocol_handler = ProtocolHandler(
        event_bus=event_bus,
        blockchain=blockchain,
        peer_manager=peer_manager,
        mempool=mempool,
        address_manager=address_manager
    )

    miner = Miner(
        event_bus=event_bus,
        blockchain=blockchain,
        mempool=mempool,
        coinbase_address=my_coinbase_address
    )
    
    # 从 AddrMan 获取种子节点，并合并 config 中的
    config_seeds = app_config['p2p'].get('peer_nodes', [])
    db_seeds = address_manager.get_peers_to_try(limit=20)
    all_seeds = config_seeds + db_seeds # (简单合并，后续可优化去重)

    # 实例化 P2P 网络"壳"
    node = P2PNode(peer_manager, all_seeds)

    # 第四步：启动节点
    log.info(f"节点 {my_node_id} 开始在端口 {listen_port} 上启动...")
    await node.start('0.0.0.0', listen_port)

if __name__ == "__main__":
    asyncio.run(main())