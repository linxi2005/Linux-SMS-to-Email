import logging
from typing import Dict, List

from modem.base import BaseModem
from modem.parser import parse_cmgl, parse_cmgr, parse_csq
from utils.helpers import now_text

LOGGER = logging.getLogger(__name__)


class EC20Modem(BaseModem):
    def initialize(self) -> Dict[str, object]:
        info = {"port": self.port, "is_online": False, "last_init_at": now_text()}
        if not self.serial_conn or not self.serial_conn.is_open:
            if not self.open():
                return info
        try:
            self.send_at("AT", timeout=3)
            self.send_at("ATE0", timeout=3)
            self.send_at("AT+CMGF=1", timeout=3)
            self.send_at('AT+CPMS="MT","MT","MT"', timeout=5)
            self.send_at("AT+CNMI=2,1,0,0,0", timeout=3)

            ati = self.send_at("ATI", timeout=3)
            model = self.send_at("AT+CGMM", timeout=3)
            firmware = self.send_at("AT+CGMR", timeout=3)
            imei = self.send_at("AT+CGSN", timeout=3)
            sim_status = self.send_at("AT+CPIN?", timeout=3)
            csq = self.send_at("AT+CSQ", timeout=3)
            operator_name = self.send_at("AT+COPS?", timeout=3)
            creg = self.send_at("AT+CREG?", timeout=3)
            cgreg = self.send_at("AT+CGREG?", timeout=3)
            iccid = self.send_at("AT+QCCID", timeout=3)
            imsi = self.send_at("AT+CIMI", timeout=3)

            signal = parse_csq(csq)
            info.update(
                {
                    "is_online": True,
                    "remark": self.remark,
                    "model": self._first_data_line(model) or self._first_data_line(ati),
                    "firmware": self._first_data_line(firmware),
                    "imei": self._first_numeric_line(imei),
                    "iccid": self._extract_after_colon(iccid),
                    "imsi": self._first_numeric_line(imsi),
                    "sim_status": self._extract_after_colon(sim_status),
                    "operator_name": self._extract_operator(operator_name),
                    "network_type": "LTE" if "1" in cgreg or "1" in creg else "",
                    "signal_raw": signal["signal_raw"],
                    "signal_percent": signal["signal_percent"],
                    "last_seen_at": now_text(),
                    "last_init_at": now_text(),
                }
            )
            LOGGER.info("模块初始化完成：%s %s", self.port, info.get("model"))
        except Exception as exc:
            LOGGER.exception("模块初始化失败 %s：%s", self.port, exc)
            info["is_online"] = False
        return info

    def read_sms(self, index: int, storage: str = "") -> Dict[str, object]:
        response = self.send_at("AT+CMGR={}".format(index), timeout=8)
        parsed = parse_cmgr(response, sms_index=index, storage=storage)
        if not parsed:
            raise ValueError("无法解析短信：{}".format(response))
        return parsed

    def list_messages(self, status: str = "ALL") -> List[Dict[str, object]]:
        response = self.send_at('AT+CMGL="{}"'.format(status), timeout=15)
        return parse_cmgl(response)

    def send_sms(self, phone: str, content: str) -> str:
        if not self.serial_conn or not self.serial_conn.is_open:
            raise RuntimeError("串口未打开")
        with self.command_lock:
            self.serial_conn.reset_input_buffer()
            self.serial_conn.write(('AT+CMGS="{}"\r'.format(phone)).encode("utf-8"))
            self.serial_conn.flush()
            prompt_deadline = 5
            for _ in range(prompt_deadline * 10):
                raw = self.serial_conn.readline()
                if b">" in raw:
                    break
            self.serial_conn.write(content.encode("utf-8") + b"\x1a")
            self.serial_conn.flush()
            lines = []
            for _ in range(60):
                raw = self.serial_conn.readline()
                if not raw:
                    continue
                line = raw.decode("utf-8", errors="ignore").strip()
                if line:
                    lines.append(line)
                if line in {"OK", "ERROR"}:
                    break
            response = "\n".join(lines)
            if "OK" not in response:
                raise RuntimeError(response or "短信发送失败")
            return response

    def mark_read(self, index: int) -> None:
        try:
            self.send_at("AT+CMGR={}".format(index), timeout=5)
        except Exception as exc:
            LOGGER.warning("标记短信已读失败 index=%s：%s", index, exc)

    def soft_reboot(self) -> str:
        return self.send_at("AT+CFUN=1,1", timeout=3, wait_ok=False)

    @staticmethod
    def _first_data_line(response: str) -> str:
        for line in (response or "").splitlines():
            line = line.strip()
            if line and line not in {"OK", "ERROR"} and not line.startswith("AT"):
                return line
        return ""

    @staticmethod
    def _first_numeric_line(response: str) -> str:
        for line in (response or "").splitlines():
            line = line.strip()
            if line.isdigit():
                return line
        return ""

    @staticmethod
    def _extract_after_colon(response: str) -> str:
        for line in (response or "").splitlines():
            if ":" in line:
                return line.split(":", 1)[1].strip().strip('"')
        return EC20Modem._first_data_line(response)

    @staticmethod
    def _extract_operator(response: str) -> str:
        parts = (response or "").split('"')
        if len(parts) >= 2:
            return parts[1]
        return ""
