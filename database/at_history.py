from typing import List

from database.database import SessionLocal
from database.models import ATHistory
from utils.helpers import now_text


def add_at_history(module_id: str, command: str, response: str, duration_ms: int, success: bool) -> None:
    session = SessionLocal()
    try:
        session.add(
            ATHistory(
                module_id=module_id,
                command=command,
                response=response,
                duration_ms=duration_ms,
                success=success,
                created_at=now_text(),
            )
        )
        session.commit()
    finally:
        session.close()


def recent_at_history(limit: int = 100) -> List[ATHistory]:
    session = SessionLocal()
    try:
        rows = session.query(ATHistory).order_by(ATHistory.id.desc()).limit(limit).all()
        for row in rows:
            session.expunge(row)
        return rows
    finally:
        session.close()
