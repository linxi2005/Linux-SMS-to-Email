import logging
from logging.handlers import RotatingFileHandler

from utils.config import LOG_DIR, ensure_runtime_dirs


def setup_logging(level_name: str = "INFO") -> None:
    ensure_runtime_dirs()
    level = getattr(logging, level_name.upper(), logging.INFO)
    formatter = logging.Formatter(
        "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    root_logger = logging.getLogger()
    root_logger.setLevel(level)
    root_logger.handlers.clear()

    file_handler = RotatingFileHandler(
        LOG_DIR / "app.log",
        maxBytes=2 * 1024 * 1024,
        backupCount=5,
        encoding="utf-8",
    )
    file_handler.setFormatter(formatter)
    file_handler.setLevel(level)

    stream_handler = logging.StreamHandler()
    stream_handler.setFormatter(formatter)
    stream_handler.setLevel(level)

    root_logger.addHandler(file_handler)
    root_logger.addHandler(stream_handler)
