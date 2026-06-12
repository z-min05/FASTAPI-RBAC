import logging
import sys
import os
from logging.handlers import RotatingFileHandler
from app.config import settings

LOG_FORMAT = "%(asctime)s | %(levelname)-8s | %(name)s:%(lineno)d - %(message)s"
DATE_FORMAT = "%Y-%m-%d %H:%M:%S"


class LevelFilter(logging.Filter):
    """只允许指定级别的日志通过"""

    def __init__(self, level: int):
        super().__init__()
        self.level = level

    def filter(self, record: logging.LogRecord) -> bool:
        return record.levelno == self.level


def _get_file_handler(filename: str, level: int | None = None) -> RotatingFileHandler:
    """创建按大小轮转的文件处理器"""
    log_dir = os.path.join(os.getcwd(), settings.LOG_FILE_DIR)
    os.makedirs(log_dir, exist_ok=True)
    filepath = os.path.join(log_dir, filename)

    handler = RotatingFileHandler(
        filepath,
        maxBytes=settings.LOG_FILE_MAX_BYTES,
        backupCount=settings.LOG_FILE_BACKUP_COUNT,
        encoding="utf-8",
    )
    handler.setFormatter(logging.Formatter(LOG_FORMAT, DATE_FORMAT))

    if level is not None:
        handler.addFilter(LevelFilter(level))

    return handler


def setup_logging() -> logging.Logger:
    log_level = getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO)

    handlers: list[logging.Handler] = [logging.StreamHandler(sys.stdout)]

    if settings.LOG_FILE_ENABLED:
        # 全量日志文件（按配置的 LOG_LEVEL 过滤）
        handlers.append(_get_file_handler("app.log"))
        # ERROR 级别单独文件
        handlers.append(_get_file_handler("error.log", level=logging.ERROR))

    logging.basicConfig(
        level=log_level,
        format=LOG_FORMAT,
        datefmt=DATE_FORMAT,
        handlers=handlers,
    )

    return logging.getLogger("fastapi-rbac")


logger = setup_logging()
