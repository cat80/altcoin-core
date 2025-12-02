import asyncio
import logging
import os
import sys
from dotenv import load_dotenv
load_dotenv()  # load env

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
from  p2p.synchronizer import Synchronizer
log = logging.getLogger(__name__)
from concurrent.futures import ProcessPoolExecutor
from multiprocessing import Manager

def load_test_app_config(port):
    return {
        'p2p': {
            "data_dir": os.path.expanduser( f"~/data/altcoin/nodes-data/node{port}"),
            "rpc_port": 8000 + port % 100, # 为每个节点分配一个RPC端口
            "listen_port": port,
            # "coinbase_address": "12T36cYGFN8yZqpDX3w5e8HucsEpfPDGsb",
            "peer_nodes": [
                {"host": "node1.altcoin.host", "port": 17890,"node_id":"node1.altcoin.host"},
                {"host": "node2.altcoin.host", "port": 17890, "node_id": "node2.altcoin.host"},
                {"local": "local.altcoin.host", "port": 17890, "node_id": "local.altcoin.host"},
            ]
        }
    }


async def main(executor: ProcessPoolExecutor, stop_event):
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
    rpc_port = app_config['p2p']['rpc_port']
    my_coinbase_address = app_config['p2p']['coinbase_address']

    # 第三步：实例化所有核心组件
    event_bus = EventBus()

    # 初始化数据库
    blockchain = Blockchain.new_from_data_dir(data_dir)

    # 为 AddressManager 创建数据库
    addr_db_path = os.path.join(data_dir, 'addr_man.db')
    addr_db_wrapper = SQLAlchemyWrapper(addr_db_path)
    
    # 为索引器和RPC创建独立的数据库
    indexer_db_path = os.path.join(data_dir, 'indexer.db')
    indexer_db_wrapper = SQLAlchemyWrapper(indexer_db_path)

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
    # 区块同步器
    synchronizer =  Synchronizer(
         blockchain,peer_manager,event_bus
    )
    protocol_handler = ProtocolHandler(
        event_bus=event_bus,
        blockchain=blockchain,
        peer_manager=peer_manager,
        mempool=mempool,
        address_manager=address_manager,
        synchronizer=synchronizer
    )

    # 必须在 ProtocolHandler 之后初始化，因为它依赖于 'reorganization_detected' 事件
    from indexer.block_indexer import BlockIndexer
    block_indexer = BlockIndexer(
        event_bus=event_bus,
        db_wrapper=indexer_db_wrapper, # 使用独立的数据库
        blockchain=blockchain
    )
    #启动索引器检查
    asyncio.create_task(block_indexer.on_block_validate(None))
    await block_indexer.on_block_validate(None)
    # 使用进程池挖矿，避免eventloop阻塞

    miner = Miner(
        event_bus=event_bus,
        blockchain=blockchain,
        mempool=mempool,
        coinbase_address=my_coinbase_address,
        executor=executor,
        stop_event=stop_event
    )

    # 启动命令检查
    if os.isatty(sys.stdin.fileno()):
        PeerCmdHandler(blockchain,peer_manager,event_bus,address_manager,miner)

    from rpc.rpc_server import RpcServer
    rpc_server = RpcServer(
        rpc_port=rpc_port,
        blockchain=blockchain,
        mempool=mempool,
        indexer_db=indexer_db_wrapper # RPC服务查询的是索引数据
    )

    # 定义索引器

    # 第四步：启动节点
    log.info(f"节点 {my_node_id} 开始在端口 {listen_port} 上启动...")
    # 使用 asyncio.gather 并发运行 P2P 节点和 RPC 服务器
    await asyncio.gather(
        node.start('0.0.0.0', listen_port),
        rpc_server.run()
    )


if __name__ == "__main__":
    # 4. 将所有多进程初始化代码放在这里
    # fast startup cmd
    # nohup python src/main.py port > ~/logs/nodes17890.log 2>&1 &
    with Manager() as manager:
        executor = ProcessPoolExecutor(max_workers=1)
        stop_mining_event = manager.Event()

        try:
            asyncio.run(main(executor, stop_mining_event))  # <--- 5. 将依赖项传入
        finally:
            # 6. 在最外层进行清理
            log.info("正在关闭挖矿进程池和管理器...")
            executor.shutdown()
            manager.shutdown()
