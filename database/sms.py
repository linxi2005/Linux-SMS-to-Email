import hashlib
from typing import Dict, List, Optional, Tuple

from sqlalchemy import or_
from sqlalchemy.exc import IntegrityError

from database.database import SessionLocal
from database.models import SMS
from utils.helpers import now_text


def make_sms_hash(phone: str, receive_time: str, content: str, imei: str) -> str:
    source = "{}|{}|{}|{}".format(phone or "", receive_time or "", content or "", imei or "")
    return hashlib.sha256(source.encode("utf-8", errors="ignore")).hexdigest()


def save_sms(data: Dict[str, object]) -> Tuple[SMS, bool]:
    session = SessionLocal()
    try:
        sms_hash = data.get("hash") or make_sms_hash(
            str(data.get("phone", "")),
            str(data.get("receive_time", "")),
            str(data.get("content", "")),
            str(data.get("imei", "")),
        )
        existing = session.query(SMS).filter(SMS.hash == sms_hash).first()
        if existing:
            return existing, False
        sms = SMS(**data)
        sms.hash = sms_hash
        session.add(sms)
        session.commit()
        session.refresh(sms)
        return sms, True
    except IntegrityError:
        session.rollback()
        existing = session.query(SMS).filter(SMS.hash == data.get("hash")).first()
        if existing:
            return existing, False
        raise
    finally:
        session.close()


def list_sms(filters: Dict[str, object], page: int, page_size: int) -> Tuple[List[SMS], int]:
    session = SessionLocal()
    try:
        query = session.query(SMS)
        keyword = str(filters.get("keyword") or "").strip()
        if keyword:
            like = "%{}%".format(keyword)
            query = query.filter(or_(SMS.phone.like(like), SMS.content.like(like), SMS.modem_name.like(like)))
        module_id = filters.get("module_id")
        if module_id:
            query = query.filter(SMS.module_id == module_id)
        phone = filters.get("phone")
        if phone:
            query = query.filter(SMS.phone.like("%{}%".format(phone)))
        forwarded = filters.get("forwarded")
        if forwarded in ("0", "1"):
            query = query.filter(SMS.forwarded == (forwarded == "1"))
        is_read = filters.get("is_read")
        if is_read in ("0", "1"):
            query = query.filter(SMS.is_read == (is_read == "1"))
        date_from = filters.get("date_from")
        if date_from:
            query = query.filter(SMS.receive_time >= date_from)
        date_to = filters.get("date_to")
        if date_to:
            query = query.filter(SMS.receive_time <= date_to + " 23:59:59")
        total = query.count()
        rows = query.order_by(SMS.receive_time.desc(), SMS.id.desc()).offset((page - 1) * page_size).limit(page_size).all()
        for row in rows:
            session.expunge(row)
        return rows, total
    finally:
        session.close()


def get_sms(sms_id: int) -> Optional[SMS]:
    session = SessionLocal()
    try:
        sms = session.query(SMS).get(sms_id)
        if sms:
            session.expunge(sms)
        return sms
    finally:
        session.close()


def mark_forward_result(sms_id: int, success: bool) -> None:
    session = SessionLocal()
    try:
        sms = session.query(SMS).get(sms_id)
        if sms:
            sms.forward_count = (sms.forward_count or 0) + 1
            sms.last_forward_time = now_text()
            if success:
                sms.forwarded = True
        session.commit()
    finally:
        session.close()


def update_read_state(ids: List[int], is_read: bool) -> None:
    session = SessionLocal()
    try:
        session.query(SMS).filter(SMS.id.in_(ids)).update({"is_read": is_read}, synchronize_session=False)
        session.commit()
    finally:
        session.close()


def delete_sms(ids: List[int]) -> None:
    session = SessionLocal()
    try:
        session.query(SMS).filter(SMS.id.in_(ids)).delete(synchronize_session=False)
        session.commit()
    finally:
        session.close()


def export_sms_rows() -> List[Dict[str, object]]:
    session = SessionLocal()
    try:
        rows = session.query(SMS).order_by(SMS.receive_time.desc()).limit(10000).all()
        return [
            {
                "id": item.id,
                "module": item.modem_name,
                "phone": item.phone,
                "receive_time": item.receive_time,
                "content": item.content,
                "encoding": item.encoding,
                "forwarded": item.forwarded,
                "is_read": item.is_read,
            }
            for item in rows
        ]
    finally:
        session.close()
