import logging
import threading
import time

from services.sms_service import SMSService
from utils.config import get_app_config

LOGGER = logging.getLogger(__name__)


class SyncService:
    def __init__(self, manager):
        self.manager = manager
        self.running = False
        self.thread = None
        self.sms_service = SMSService(manager)

    def start(self) -> None:
        if self.thread and self.thread.is_alive():
            return
        self.running = True
        self.thread = threading.Thread(target=self._loop, name="sms-sync", daemon=True)
        self.thread.start()

    def stop(self) -> None:
        self.running = False

    def _loop(self) -> None:
        while self.running:
            config = get_app_config()
            interval = max(30, int(config.get("sync_interval_seconds", 30)))
            for module_id in list(self.manager.modems.keys()):
                count = self.sms_service.sync_module_messages(module_id)
                if count:
                    LOGGER.info("模块 %s 同步新增短信：%s", module_id, count)
            time.sleep(interval)
