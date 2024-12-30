from loguru import logger as loguru_logger
import sys
from pathlib import Path


def setup_logger():
    # 获取日志文件路径
    log_path = Path("logs")
    log_path.mkdir(exist_ok=True)

    # 移除默认的 handler
    loguru_logger.remove()

    # 添加控制台 handler
    loguru_logger.add(
        sys.stdout,
        format="<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> | "
        "<level>{level: <8}</level> | "
        "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> | "
        "<level>{message}</level>",
        level="INFO",
        colorize=True,
    )

    # 添加文件 handler
    loguru_logger.add(
        log_path / "app_{time:YYYY-MM-DD}.log",
        rotation="00:00",
        retention="7 days",
        format="{time:YYYY-MM-DD HH:mm:ss.SSS} | {level: <8} | {name}:{function}:{line} | {message}",
        level="DEBUG",
        encoding="utf-8",
    )

    return loguru_logger


# 初始化并导出 logger
logger = setup_logger()
