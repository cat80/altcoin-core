import logging
import os
import sys
from pathlib import Path
import hashlib
from utils.crypto import *
from utils.crypto import generate_keypair, get_address_by_public_key

log = logging.getLogger(__name__)

def setup_node(config: dict):
    """
    初始化节点，包括创建目录、文件锁、生成/加载密钥。
    """
    data_dir = Path(config['p2p']['data_dir'])
    lock_file_path = data_dir / '.lock'
    key_file_path = data_dir / 'node_key'

    # 1. 确保数据目录存在
    try:
        data_dir.mkdir(parents=True, exist_ok=True)
        log.info(f"数据目录已确保存在: {data_dir}")
    except OSError as e:
        log.debug(f"Exception details for creating data directory {data_dir}:", exc_info=True)
        log.error(f"无法创建数据目录 {data_dir}: {e}")
        sys.exit(1)

    # 2. 处理文件锁
    try:
        if lock_file_path.exists():
            with open(lock_file_path, 'r') as f:
                pid = int(f.read())
            # 检查PID是否仍在运行 (这是一个简单的检查，可能不完全可靠)
            try:
                os.kill(pid, 0)
                log.error(f"节点已在运行 (PID: {pid})，请先停止它。")
                sys.exit(1)
            except OSError:
                log.debug(f"Exception details for checking PID {pid}:", exc_info=True)
                log.warning(f"检测到残留的锁文件 (来自已退出的PID: {pid})，将继续启动。")
        
        with open(lock_file_path, 'w') as f:
            f.write(str(os.getpid()))
        log.info(f"已成功获取数据目录锁: {lock_file_path}")

    except Exception as e:
        log.debug("Exception details for lock file operations:", exc_info=True)
        log.error(f"无法创建或检查锁文件: {e}")
        sys.exit(1)

    # 3. 生成/加载密钥对
    if key_file_path.exists():
        log.info(f"从 {key_file_path} 加载现有密钥...")
        private_key, public_key = load_key_from_pem(key_file_path)
    else:
        log.info("未找到密钥文件，正在生成新的密钥对...")
        private_key, public_key = generate_keypair()
        save_to_pem(private_key,key_file_path)
        log.info(f"新密钥已保存到: {key_file_path}")

    # 4. 生成 Node ID 和 Coinbase 地址
    node_id = hashlib.sha256(public_key.to_string()).hexdigest()
    coinbase_address = get_address_by_public_key(public_key)

    log.info(f"节点ID: {node_id}")
    log.info(f"默认Coinbase地址: {coinbase_address}")

    # 5. 更新配置
    if not config['p2p'].get('coinbase_address'):
        config['p2p']['coinbase_address'] = coinbase_address
        log.info("配置中的coinbase_address为空，已使用节点公钥地址填充。")
    
    return node_id, config
