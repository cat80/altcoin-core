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
print(__name__)
print(os.pardir)
from utils import setup_logging,load_app_config
app_config =None
# (你需要一个函数来加载或生成节点ID)
def get_node_id(data_dir):
    # 1. 检查 data/node_key 文件是否存在
    # 2. 如果存在，加载私钥并生成 Node ID (例如 公钥的哈希)
    # 3. 如果不存在，生成新的密钥对，保存私钥，返回 Node ID
    return "my-unique-node-id-12345"

async def main():
    # 第一步加载日志配置
    # 加载默认的日志
    setup_logging()
    log = logging.getLogger(__name__)
    # 加载当前配置
    global app_config
    app_config = load_app_config()

    log.debug(f'load app config:{app_config}')
    data_dir = app_config['p2p']['data_dir']
    listen_port = app_config['p2p']['listen_port']
    # 1. 加载配置和节点ID
    my_node_id = get_node_id(data_dir)
    # 这里
    my_coinbase_address = app_config['p2p']['coinbase_address'] # 应从钱包加载

    # 2. 实例化所有核心组件
    event_bus = EventBus()
    blockchain = Blockchain.new_from_data_dir(data_dir)
    mempool = Mempool(event_bus)

    # 3. 注入依赖
    peer_manager = PeerManager(event_bus, my_node_id)

    # 4. 注册所有业务逻辑处理器
    #    (注意：它们只与 EventBus 和其他服务交互)
    protocol_handler = ProtocolHandler(
        event_bus=event_bus,
        blockchain=blockchain,
        peer_manager=peer_manager,
        mempool=mempool
    )

    miner = Miner(
        event_bus=event_bus,
        blockchain=blockchain,
        mempool=mempool,
        coinbase_address=my_coinbase_address
    )
    # 5. 实例化 P2P 网络"壳"
    node = P2PNode(peer_manager, app_config['p2p']['peer_nodes'])

    # 6. 启动节点 (服务器和客户端连接)
    print(f"Starting node {my_node_id} on port {listen_port}...")
    await node.start('0.0.0.0', listen_port)

if __name__ == "__main__":
    asyncio.run(main())
