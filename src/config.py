import os
import configparser
from pathlib import Path

class Config:
    """
    配置类，用于加载和提供对.ini配置文件的访问。
    """

    def __init__(self, config_file,cli_data_dir:str,cli_port:int):
        self.parser = configparser.ConfigParser(interpolation=configparser.ExtendedInterpolation())

        if config_file and  os.path.exists(config_file):
            self.parser.read(config_file)
        else:
            print(f'config file not exists,use temp config')
        self.base_dir = cli_data_dir
        if not self.base_dir.endswith('/'):
            self.base_dir = self.base_dir + '/'
        self.node_listen_port = cli_port # 监听端口

        # 日志配置
        self.log_level = self.parser.get('logging', 'level', fallback='INFO')
        self.log_dir = self.parser.get('logging', 'directory', fallback=f'{self.base_dir}/logs/')

        # 存储配置
        self.block_dir = f"{self.base_dir}/blocks/"
        self.rocksdb_dir = f"{self.base_dir}/utxo/"
        self.sqlite_path =f"{self.base_dir}/index.db"

        # 确保目录存在
        self._create_dirs()

    def _create_dirs(self):
        """确保所有配置的目录都存在。"""
        os.makedirs(self.log_dir, exist_ok=True)
        os.makedirs(self.block_dir, exist_ok=True)
        os.makedirs(self.rocksdb_dir, exist_ok=True)
        # SQLite的目录是文件所在的目录
        os.makedirs(os.path.dirname(self.sqlite_path), exist_ok=True)



def load_config(env,cli_data_dir,cli_port=1989) -> Config:
    """
    根据环境变量 ALTCOIN_ENV 加载配置。
    默认为 'dev' 环境。
    """
    config_filename = f"{env}.ini"
    cwd = Path.cwd()

    config_full_path = Path(  os.path.join(cwd,config_filename))
    exists_config_file = None
    # 对当前工作目录往上一级级找.ini 配置
    for parent_dir_item in config_full_path.parents:
        current_try_config_path = parent_dir_item.joinpath(config_filename)
        if current_try_config_path.is_file():
            exists_config_file = current_try_config_path
    if exists_config_file:
        print(f"Loading configuration for '{env}' environment from '{exists_config_file.resolve()}'...")
    else:
        print(f"Loading configuration for '{env}' environment from '{env}'.ini not exists use default config.")
    return Config(  exists_config_file.resolve() if exists_config_file else None,cli_data_dir,cli_port)

# 在模块加载时，就执行加载配置的操作


# 定义一些常量
MAGIC_BYTES = b'\xab\xcd\xcd\xef' # 定义区块的头

# 初始的代币奖励数量
INITIAL_BLOCK_REWARD = 10 * 100_000_000 # 10个奖励
REWARD_CUTOFF_BLOCKS = 2100000 # 每210万个区块减半

# 难度调整区块数，目前一分钟一个区块，每一周调整一次难度
ADJUSTMENT_INTERVAL = 10080
TARGET_TIMESPAN = 10080 * 60  # 一周的秒数
# INITIAL_BITS = 2083236893 503497599
INITIAL_BITS =  503842407
# 定义区块状态的常量
BLOCK_STATUS_VALID = 1  # 表示区块头和内容都已完全验证
BLOCK_STATUS_FORK = 0 # 表示区块为侧链
BLOCK_STATUS_INVALID = -1 # 表示区块头和内容有为废除区域，一般重组失败后置为无效