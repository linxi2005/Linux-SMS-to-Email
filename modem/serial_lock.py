import logging
import os

try:
    import fcntl
except ImportError:  # pragma: no cover - target runtime is Linux.
    fcntl = None

LOGGER = logging.getLogger(__name__)


class SerialExclusiveLock:
    def __init__(self, file_descriptor):
        self.file_descriptor = file_descriptor
        self.locked = False

    def acquire(self) -> bool:
        if fcntl is None or os.name != "posix":
            LOGGER.warning("当前系统不支持 fcntl 串口独占锁，仅允许用于开发预览：%s", os.name)
            self.locked = False
            return True
        try:
            fcntl.flock(self.file_descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
            self.locked = True
            return True
        except (OSError, AttributeError) as exc:
            LOGGER.error("串口独占锁失败：%s", exc)
            return False

    def release(self) -> None:
        if not self.locked:
            return
        if fcntl is None:
            self.locked = False
            return
        try:
            fcntl.flock(self.file_descriptor, fcntl.LOCK_UN)
        except OSError as exc:
            LOGGER.warning("释放串口独占锁失败：%s", exc)
        finally:
            self.locked = False
