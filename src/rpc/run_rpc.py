import logging
import os
import asyncio

# 导入你封装好的 RpcServer 类
from rpc.rpc_server import RpcServer

# 导入需要注入的核心组件
from core.blockchain import Blockchain
from mempool.mempool import Mempool
from storage.sql_alchemy_wrapper import SQLAlchemyWrapper
from p2p.event_bus import EventBus

# 配置日志
from config import  setup_logging
setup_logging()
log = logging.getLogger(__name__)

# --- 配置 ---
# 使用与集成测试相同的节点数据目录
DATA_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "nodes-data", "node17880-test"))
INDEXER_DB_PATH = os.path.join(DATA_DIR, "indexer_test.db")
RPC_PORT = 8332

async def main():
    """
    初始化所有依赖项并启动 RpcServer。
    """
    log.info("正在启动 RPC 服务器...")
    log.info(f"使用测试数据目录: {DATA_DIR}")

    # 1. 初始化核心组件
    log.info("初始化 Blockchain 核心...")
    blockchain = Blockchain.new_from_data_dir(DATA_DIR)
    log.info("初始化 EventBus...")
    event_bus = EventBus()
    log.info("初始化 Mempool...")
    mempool = Mempool(event_bus ,blockchain)
    

    
    log.info(f"初始化 Indexer 数据库: {INDEXER_DB_PATH}")

    indexer_db_wrapper = SQLAlchemyWrapper(INDEXER_DB_PATH)


    # 3. 创建 RpcServer 实例，注入所有依赖项
    log.info("创建 RpcServer 实例...")
    rpc_server = RpcServer(
        rpc_port=RPC_PORT,
        blockchain=blockchain,
        mempool=mempool,
        event_bus=event_bus,
        indexer_db=indexer_db_wrapper
    )
    
    # 4. 运行 RpcServer
    # RpcServer 内部的 run 方法是异步的，所以我们 await 它
    try:
        await rpc_server.run()
    finally:
        # 在服务器关闭时，确保数据库连接被正确关闭
        log.info("RPC 服务器正在关闭，清理资源...")
        blockchain.close()
        indexer_db_wrapper.close()
        log.info("资源清理完毕。")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        log.info("通过键盘中断请求关闭服务器。")
