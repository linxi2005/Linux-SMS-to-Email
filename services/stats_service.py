import os
import shutil
import sqlite3
from pathlib import Path
from typing import Dict

import psutil
from sqlalchemy import func

from database.database import DB_PATH, SessionLocal
from database.models import MailLog, Modem, SMS
from utils.config import BACKUP_DIR
from utils.helpers import now_text

START_TIME = now_text()


def dashboard_stats() -> Dict[str, object]:
    session = SessionLocal()
    try:
        today = now_text()[:10]
        return {
            "start_time": START_TIME,
            "modem_count": session.query(Modem).count(),
            "online_modem_count": session.query(Modem).filter(Modem.is_online == True).count(),
            "sms_count": session.query(SMS).count(),
            "today_sms_count": session.query(SMS).filter(SMS.receive_time.like(today + "%")).count(),
            "forward_success_today": session.query(SMS).filter(SMS.forwarded == True, SMS.last_forward_time.like(today + "%")).count(),
            "forward_fail_today": session.query(MailLog).filter(MailLog.success == False, MailLog.sent_at.like(today + "%")).count(),
            "cpu_percent": psutil.cpu_percent(interval=0.1),
            "memory_percent": psutil.virtual_memory().percent,
            "disk_percent": psutil.disk_usage(str(Path.cwd())).percent,
        }
    finally:
        session.close()


def database_stats() -> Dict[str, object]:
    session = SessionLocal()
    try:
        size = os.path.getsize(DB_PATH) if os.path.exists(DB_PATH) else 0
        return {
            "db_path": str(DB_PATH),
            "db_size": size,
            "sms_count": session.query(SMS).count(),
            "modem_count": session.query(Modem).count(),
            "mail_success": session.query(MailLog).filter(MailLog.success == True).count(),
            "mail_failed": session.query(MailLog).filter(MailLog.success == False).count(),
        }
    finally:
        session.close()


def vacuum_database() -> None:
    connection = sqlite3.connect(str(DB_PATH))
    try:
        connection.execute("VACUUM")
    finally:
        connection.close()


def integrity_check() -> str:
    connection = sqlite3.connect(str(DB_PATH))
    try:
        row = connection.execute("PRAGMA integrity_check").fetchone()
        return row[0] if row else "unknown"
    finally:
        connection.close()


def backup_database() -> str:
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    target = BACKUP_DIR / "sms-{}.db".format(now_text().replace(":", "").replace(" ", "-"))
    shutil.copy2(DB_PATH, target)
    return str(target)


def restore_database(source_path: str) -> None:
    if not source_path:
        raise ValueError("未提供恢复文件")
    backup_database()
    shutil.copy2(source_path, DB_PATH)


def delete_sms_older_than(days: int) -> int:
    if days <= 0:
        return 0
    connection = sqlite3.connect(str(DB_PATH))
    try:
        cursor = connection.execute(
            "DELETE FROM sms WHERE receive_time < datetime('now', ?)",
            ("-{} days".format(days),),
        )
        connection.commit()
        return cursor.rowcount
    finally:
        connection.close()


def keep_latest_sms(max_count: int) -> int:
    if max_count <= 0:
        return 0
    connection = sqlite3.connect(str(DB_PATH))
    try:
        cursor = connection.execute(
            "DELETE FROM sms WHERE id NOT IN (SELECT id FROM sms ORDER BY receive_time DESC, id DESC LIMIT ?)",
            (max_count,),
        )
        connection.commit()
        return cursor.rowcount
    finally:
        connection.close()
