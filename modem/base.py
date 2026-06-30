import logging
import threading
import time
from typing import Callable, Optional

import serial

from modem.serial_lock import SerialExclusiveLock

LOGGER = logging.getLogger(__name__)


class BaseModem:
    def __init__(self, module_id: str, port: str, remark: str = "", baudrate: int = 115200):
        self.module_id = module_id
        self.port = port
        self.remark = remark or port
        self.baudrate = baudrate
        self.serial_conn = None
        self.serial_lock = None
        self.command_lock = threading.RLock()
        self.running = False
        self.listener_thread = None
        self.on_line: Optional[Callable[[str], None]] = None

    def open(self) -> bool:
        try:
            self.serial_conn = serial.Serial(
                self.port,
                self.baudrate,
                timeout=1,
                write_timeout=3,
            )
            self.serial_lock = SerialExclusiveLock(self.serial_conn.fileno())
            if not self.serial_lock.acquire():
                self.close()
                return False
            LOGGER.info("串口已打开并独占锁定：%s", self.port)
            return True
        except serial.SerialException as exc:
            LOGGER.error("打开串口失败 %s：%s", self.port, exc)
            self.serial_conn = None
            return False

    def close(self) -> None:
        self.running = False
        if self.serial_lock:
            self.serial_lock.release()
            self.serial_lock = None
        if self.serial_conn:
            try:
                self.serial_conn.close()
            except serial.SerialException:
                pass
            self.serial_conn = None

    def send_at(self, command: str, timeout: float = 5.0, wait_ok: bool = True) -> str:
        if not self.serial_conn or not self.serial_conn.is_open:
            raise RuntimeError("串口未打开")
        with self.command_lock:
            self.serial_conn.reset_input_buffer()
            self.serial_conn.write((command + "\r").encode("utf-8"))
            self.serial_conn.flush()
            deadline = time.time() + timeout
            lines = []
            while time.time() < deadline:
                raw = self.serial_conn.readline()
                if not raw:
                    continue
                line = raw.decode("utf-8", errors="ignore").strip()
                if not line:
                    continue
                lines.append(line)
                if wait_ok and line in {"OK", "ERROR"}:
                    break
            return "\n".join(lines)

    def start_listener(self, on_line: Callable[[str], None]) -> None:
        self.on_line = on_line
        if self.listener_thread and self.listener_thread.is_alive():
            return
        self.running = True
        self.listener_thread = threading.Thread(target=self._listen_loop, name="listen-{}".format(self.port), daemon=True)
        self.listener_thread.start()

    def _listen_loop(self) -> None:
        LOGGER.info("开始监听串口：%s", self.port)
        while self.running:
            try:
                if not self.serial_conn or not self.serial_conn.is_open:
                    time.sleep(1)
                    continue
                raw = self.serial_conn.readline()
                if not raw:
                    continue
                line = raw.decode("utf-8", errors="ignore").strip()
                if line and self.on_line:
                    self.on_line(line)
            except Exception as exc:
                LOGGER.exception("监听串口异常 %s：%s", self.port, exc)
                time.sleep(2)
