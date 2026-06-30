import logging
import threading
import time
from typing import Dict, Optional

from database import modem as modem_db
from modem.ec20 import EC20Modem
from modem.parser import parse_cmti
from services.sms_service import SMSService
from utils.config import get_app_config, get_modem_config

LOGGER = logging.getLogger(__name__)


class ModemManager:
    def __init__(self):
        self.modems: Dict[str, EC20Modem] = {}
        self.sms_service = SMSService(self)
        self.running = False
        self.monitor_thread = None

    def load_configured_modems(self) -> None:
        modem_db.sync_config_to_db()
        config = get_modem_config()
        for item in config.get("modems", []):
            if not item.get("enabled", True):
                continue
            port = item.get("port")
            if not port:
                continue
            module_id = modem_db.module_id_for_port(port)
            if module_id not in self.modems:
                self.modems[module_id] = EC20Modem(module_id, port, item.get("remark") or port)

    def start(self) -> None:
        self.running = True
        self.load_configured_modems()
        for module_id in list(self.modems.keys()):
            self.initialize_modem(module_id)
        self.monitor_thread = threading.Thread(target=self._monitor_loop, name="modem-monitor", daemon=True)
        self.monitor_thread.start()

    def stop(self) -> None:
        self.running = False
        for modem in self.modems.values():
            modem.close()

    def initialize_modem(self, module_id: str) -> bool:
        modem = self.modems.get(module_id)
        if not modem:
            return False
        info = modem.initialize()
        modem_db.update_modem_status(module_id, info)
        if info.get("is_online"):
            modem.start_listener(lambda line, mid=module_id: self.handle_line(mid, line))
            return True
        return False

    def handle_line(self, module_id: str, line: str) -> None:
        cmti = parse_cmti(line)
        if cmti:
            LOGGER.info("收到短信通知：Storage: %s Index: %s", cmti["storage"], cmti["index"])
            self.sms_service.handle_cmti(module_id, str(cmti["storage"]), int(cmti["index"]))

    def get_modem(self, module_id: str) -> Optional[EC20Modem]:
        return self.modems.get(module_id)

    def reload(self) -> None:
        config = get_modem_config()
        configured = {
            modem_db.module_id_for_port(item.get("port"))
            for item in config.get("modems", [])
            if item.get("port") and item.get("enabled", True)
        }
        for module_id in list(self.modems.keys()):
            if module_id not in configured:
                self.modems[module_id].close()
                self.modems.pop(module_id, None)
        known = set(self.modems.keys())
        self.load_configured_modems()
        current = set(self.modems.keys())
        for module_id in current:
            if module_id not in known:
                self.initialize_modem(module_id)

    def soft_reboot(self, module_id: str) -> bool:
        modem = self.get_modem(module_id)
        if not modem:
            return False
        try:
            LOGGER.warning("准备软重启模块：%s", modem.port)
            modem.soft_reboot()
            modem.close()
            time.sleep(8)
            return self.initialize_modem(module_id)
        except Exception as exc:
            LOGGER.exception("模块软重启失败：%s", exc)
            return False

    def _monitor_loop(self) -> None:
        config = get_app_config()
        interval = max(60, int(config.get("heartbeat_interval_seconds", 120)))
        reconnect_delay = max(30, int(config.get("reconnect_initial_seconds", 30)))
        max_delay = max(reconnect_delay, int(config.get("reconnect_max_seconds", 600)))
        failures: Dict[str, int] = {}
        while self.running:
            time.sleep(interval)
            for module_id, modem in list(self.modems.items()):
                try:
                    if not modem.serial_conn or not modem.serial_conn.is_open:
                        failures[module_id] = min(max_delay, failures.get(module_id, reconnect_delay) * 2)
                        LOGGER.warning("模块离线，延后重连：%s delay=%s", modem.port, failures[module_id])
                        modem_db.update_modem_status(module_id, {"is_online": False, "port": modem.port})
                        continue
                    response = modem.send_at("AT", timeout=3)
                    if "OK" in response:
                        failures[module_id] = reconnect_delay
                        modem_db.update_modem_status(module_id, {"is_online": True, "port": modem.port})
                except Exception as exc:
                    LOGGER.warning("模块保活失败 %s：%s", modem.port, exc)
                    modem_db.update_modem_status(module_id, {"is_online": False, "port": modem.port})
