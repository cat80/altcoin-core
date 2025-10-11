import logging
import sys
from logging.handlers import TimedRotatingFileHandler
from config import config  # 导入我们的配置对象


def setup_logger(name="AltCoin"):
    """
    根据配置设置日志，支持控制台输出和按天轮转的文件输出。
    """
    log_level = getattr(logging, config.log_level.upper(), logging.INFO)

    logger = logging.getLogger(name)
    logger.setLevel(log_level)

    # 防止重复添加handler
    if logger.hasHandlers():
        logger.handlers.clear()

    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')

    # 控制台输出
    stdout_handler = logging.StreamHandler(sys.stdout)
    stdout_handler.setFormatter(formatter)
    logger.addHandler(stdout_handler)

    # 文件输出，按天轮转，保留7天
    log_file_path = f"{config.log_dir}/altcoin.log"
    file_handler = TimedRotatingFileHandler(log_file_path, when="midnight", interval=1, backupCount=7)
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    logger.info(f"Logger initialized. Log level: {config.log_level}, Log file: {log_file_path}")
    return logger