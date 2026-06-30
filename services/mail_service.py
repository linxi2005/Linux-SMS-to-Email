import logging
import smtplib
from email.mime.text import MIMEText
from typing import Dict, Iterable, Tuple

from database.mail import add_mail_log
from database.sms import get_sms, mark_forward_result
from utils.config import get_mail_config
from utils.helpers import now_text

LOGGER = logging.getLogger(__name__)


def render_template(template: str, values: Dict[str, object]) -> str:
    rendered = template or ""
    for key, value in values.items():
        rendered = rendered.replace("{{" + key + "}}", str(value if value is not None else ""))
    return rendered


class MailService:
    def __init__(self):
        self.config = get_mail_config()

    def reload(self) -> None:
        self.config = get_mail_config()

    def send_for_sms(self, sms_id: int, extra_values: Dict[str, object] = None) -> bool:
        self.reload()
        sms = get_sms(sms_id)
        if not sms:
            return False
        values = {
            "phone": sms.phone,
            "content": sms.content,
            "time": sms.receive_time,
            "carrier": extra_values.get("carrier", "") if extra_values else "",
            "imei": sms.imei,
            "signal": extra_values.get("signal", "") if extra_values else "",
            "operator": extra_values.get("operator", "") if extra_values else "",
            "module_name": sms.modem_name,
            "module_port": extra_values.get("module_port", "") if extra_values else "",
            "module_model": sms.modem_model,
        }
        success = self.send_message(
            recipients=self.config.get("recipients", []),
            subject=render_template(self.config.get("subject_template", "新短信"), values),
            body=render_template(self.config.get("body_template", "{{content}}"), values),
            sms_id=sms_id,
        )
        mark_forward_result(sms_id, success)
        return success

    def send_manual_message(self, message: Dict[str, object], recipients: Iterable[str] = None) -> bool:
        values = {
            "phone": message.get("phone", ""),
            "content": message.get("content", ""),
            "time": message.get("receive_time", now_text()),
            "carrier": "",
            "imei": message.get("imei", ""),
            "signal": "",
            "operator": "",
            "module_name": message.get("modem_name", ""),
            "module_port": message.get("module_port", ""),
            "module_model": message.get("modem_model", ""),
        }
        return self.send_message(
            recipients=recipients or self.config.get("recipients", []),
            subject=render_template(self.config.get("subject_template", "新短信"), values),
            body=render_template(self.config.get("body_template", "{{content}}"), values),
            sms_id=None,
        )

    def send_message(self, recipients: Iterable[str], subject: str, body: str, sms_id=None) -> bool:
        self.reload()
        if not self.config.get("enabled"):
            LOGGER.warning("邮件转发未启用")
            return False
        recipients = [item.strip() for item in recipients if str(item).strip()]
        if not recipients:
            LOGGER.warning("没有配置收件人")
            return False
        all_success = True
        for recipient in recipients:
            ok, error = self._send_one(recipient, subject, body)
            add_mail_log(sms_id, recipient, ok, error)
            all_success = all_success and ok
            if ok:
                LOGGER.info("短信转发成功：%s", recipient)
            else:
                LOGGER.error("短信转发失败：%s %s", recipient, error)
        return all_success

    def _send_one(self, recipient: str, subject: str, body: str) -> Tuple[bool, str]:
        try:
            message = MIMEText(body, "plain", "utf-8")
            message["Subject"] = subject
            message["From"] = self.config.get("from_email") or self.config.get("username")
            message["To"] = recipient
            timeout = int(self.config.get("timeout_seconds") or 20)
            server_name = self.config.get("smtp_server")
            port = int(self.config.get("port") or 465)
            if self.config.get("use_ssl"):
                smtp = smtplib.SMTP_SSL(server_name, port, timeout=timeout)
            else:
                smtp = smtplib.SMTP(server_name, port, timeout=timeout)
            with smtp:
                if self.config.get("use_tls") and not self.config.get("use_ssl"):
                    smtp.starttls()
                username = self.config.get("username")
                password = self.config.get("password")
                if username:
                    smtp.login(username, password)
                smtp.sendmail(message["From"], [recipient], message.as_string())
            return True, ""
        except Exception as exc:
            return False, str(exc)
