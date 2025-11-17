import asyncio
import logging
import os
import sys

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
from p2p.peer_cmd_handler import PeerCmdHandler
log = logging.getLogger(__name__)


def load_test_app_config(port):
    return {
        'p2p': {
            "data_dir": f"/mnt/d/prj/web3/altcoin-core/nodes-data/node{port}",
            "listen_port": port,
            "coinbase_address": "12T36cYGFN8yZqpDX3w5e8HucsEpfPDGsb",
            "peer_nodes": [
                {"host": "127.0.0.1", "port": 17890,"node_id":"17890"},
                {"host": "127.0.0.1", "port": 17880, "node_id": "17880"}
            ]
        }
    }


async def main():
    # 第一步：加载日志和应用配置

    listen_port = 17890
    if len(sys.argv) > 1:
        listen_port = int(sys.argv[-1])
    app_config = load_test_app_config(listen_port)

    log.debug(f'原始应用配置: {app_config}')

    # 第二步：初始化节点环境（目录、锁、密钥）
    my_node_id, app_config = setup_node(app_config)

    new_logs_dir = f'{app_config["p2p"]["data_dir"]}/logs/log-{listen_port}.log'

    setup_logging(log_filename=new_logs_dir)
    # 从最终配置中获取参数
    data_dir = app_config['p2p']['data_dir']
    listen_port = app_config['p2p']['listen_port']
    my_coinbase_address = app_config['p2p']['coinbase_address']

    # 第三步：实例化所有核心组件
    event_bus = EventBus()

    # 初始化数据库
    blockchain = Blockchain.new_from_data_dir(data_dir)

    addr_db_path = os.path.join(data_dir, 'addr_man.db')
    addr_db_wrapper = SQLAlchemyWrapper(addr_db_path)
    
    mempool = Mempool(event_bus,blockchain)

    # --- 解析循环依赖 ---
    # 1. 提前创建 Node 和 AddressManager 的“空”实例
    node = P2PNode() # PeerManager 稍后注入
    # AddressManager 的回调也稍后注入
    address_manager = AddressManager(addr_db_wrapper,app_config['p2p']['peer_nodes'], active_peers_getter = lambda :set())

    # 2. 创建 PeerManager，此时依赖项已存在
    peer_manager = PeerManager(
        event_bus=event_bus,
        my_node_id=my_node_id,
        my_listen_port=listen_port,
        address_manager=address_manager,
        node=node
    )

    # 3. 完成注入
    node.peer_manager = peer_manager
    address_manager.get_active_node_ids = peer_manager.get_active_node_ids

    # --- 依赖注入完成 ---

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

    # 启动命令检查
    PeerCmdHandler(blockchain,peer_manager,event_bus,address_manager,miner)

    # 第四步：启动节点
    log.info(f"节点 {my_node_id} 开始在端口 {listen_port} 上启动...")
    await node.start('0.0.0.0', listen_port)


if __name__ == "__main__":
    asyncio.run(main())
