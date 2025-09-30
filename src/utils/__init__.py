"""
Utility module for Altcoin.
Contains general utility functions.
"""
from .crypto import  *
from .merkle_tree import MerkleTree

from .logger import setup_logger
from .exceptions import *

# 1. 创建全局日志
log = setup_logger()

log.info("Utility services initialized.")