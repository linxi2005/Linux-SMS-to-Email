from typing import List

from database.database import SessionLocal
from database.models import MailLog
from utils.helpers import now_text


def add_mail_log(sms_id, recipient: str, success: bool, error_message: str = "") -> None:
    session = SessionLocal()
    try:
        session.add(
            MailLog(
                sms_id=sms_id,
                recipient=recipient,
                success=success,
                error_message=error_message or "",
                sent_at=now_text(),
            )
        )
        session.commit()
    finally:
        session.close()


def recent_mail_logs(limit: int = 100) -> List[MailLog]:
    session = SessionLocal()
    try:
        rows = session.query(MailLog).order_by(MailLog.id.desc()).limit(limit).all()
        for row in rows:
            session.expunge(row)
        return rows
    finally:
        session.close()
