import logging
import os
from logging.handlers import RotatingFileHandler

def setup_logger():
    """
    初始化并配置全局日志系统
    - 写入终端 (控制台输出)
    - 写入文件 weibo_bot.log（最大 5MB，保留 3 个备份）
    """
    logger = logging.getLogger("WeiboBot")
    
    # 如果已经配置过，直接返回避免重复添加 handler
    if logger.handlers:
        return logger

    logger.setLevel(logging.INFO)

    # 日志格式: [2026-03-20 12:00:00] [INFO] [server.py:42] - 消息内容
    formatter = logging.Formatter(
        '[%(asctime)s] [%(levelname)s] [%(filename)s:%(lineno)d] - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )

    # 1. 终端输出 Handler
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    # 2. 文件写入 Handler (5MB 滚动)
    log_file = os.path.join(os.path.dirname(__file__), 'weibo_bot.log')
    file_handler = RotatingFileHandler(log_file, maxBytes=5*1024*1024, backupCount=3, encoding='utf-8')
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    return logger

# 全局单例 logger 实例
logger = setup_logger()
