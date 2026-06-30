import logging
from typing import Dict, List

from database import modem as modem_db
from database.sms import save_sms
from services.mail_service import MailService
from utils.helpers import now_text

LOGGER = logging.getLogger(__name__)


class SMSService:
    def __init__(self, manager):
        self.manager = manager
        self.mail_service = MailService()

    def handle_cmti(self, module_id: str, storage: str, index: int) -> None:
        modem = self.manager.get_modem(module_id)
        modem_info = modem_db.get_modem(module_id)
        if not modem:
            LOGGER.error("收到短信通知但模块不存在：%s", module_id)
            return
        try:
            LOGGER.info("开始读取短信...")
            message = modem.read_sms(index, storage)
            self._enrich_message(module_id, message, modem_info)
            sms, created = save_sms(message)
            LOGGER.info("发送人：%s", message.get("phone"))
            LOGGER.info("时间：%s", message.get("receive_time"))
            LOGGER.info("编码：%s", message.get("encoding"))
            LOGGER.info("内容：%s", message.get("content"))
            LOGGER.info("短信已保存 SQLite。" if created else "短信已存在 SQLite，跳过去重写入。")
            try:
                modem.mark_read(index)
            except Exception as exc:
                LOGGER.warning("短信标记已读失败：%s", exc)
            self.mail_service.send_for_sms(
                sms.id,
                {
                    "operator": getattr(modem_info, "operator_name", ""),
                    "signal": getattr(modem_info, "signal_raw", ""),
                    "module_port": getattr(modem_info, "port", ""),
                },
            )
        except Exception as exc:
            LOGGER.exception("处理新短信失败 index=%s：%s", index, exc)

    def sync_module_messages(self, module_id: str) -> int:
        modem = self.manager.get_modem(module_id)
        modem_info = modem_db.get_modem(module_id)
        if not modem:
            return 0
        count = 0
        try:
            for message in modem.list_messages("ALL"):
                self._enrich_message(module_id, message, modem_info)
                message["is_synced"] = True
                sms, created = save_sms(message)
                if created:
                    count += 1
                if not sms.forwarded:
                    self.mail_service.send_for_sms(
                        sms.id,
                        {
                            "operator": getattr(modem_info, "operator_name", ""),
                            "signal": getattr(modem_info, "signal_raw", ""),
                            "module_port": getattr(modem_info, "port", ""),
                        },
                    )
        except Exception as exc:
            LOGGER.exception("同步模块短信失败：%s", exc)
        return count

    def read_module_messages_for_display(self, module_id: str, status: str = "ALL") -> List[Dict[str, object]]:
        modem = self.manager.get_modem(module_id)
        modem_info = modem_db.get_modem(module_id)
        if not modem:
            return []
        messages = modem.list_messages(status)
        for message in messages:
            self._enrich_message(module_id, message, modem_info)
        return messages

    def _enrich_message(self, module_id: str, message: Dict[str, object], modem_info) -> None:
        message.update(
            {
                "module_id": module_id,
                "modem_name": getattr(modem_info, "remark", "") or getattr(modem_info, "port", ""),
                "modem_model": getattr(modem_info, "model", "EC20") or "EC20",
                "imei": getattr(modem_info, "imei", ""),
                "sync_time": now_text(),
            }
        )
