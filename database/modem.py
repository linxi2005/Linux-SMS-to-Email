import uuid
from typing import Dict, List, Optional

from database.database import SessionLocal
from database.models import Modem
from utils.config import get_modem_config, save_modem_config
from utils.helpers import now_text


def module_id_for_port(port: str) -> str:
    return uuid.uuid5(uuid.NAMESPACE_URL, "ec20:{}".format(port)).hex


def sync_config_to_db() -> None:
    config = get_modem_config()
    session = SessionLocal()
    try:
        for item in config.get("modems", []):
            port = item.get("port")
            if not port:
                continue
            module_id = module_id_for_port(port)
            modem = session.query(Modem).filter(Modem.module_id == module_id).first()
            if not modem:
                modem = Modem(module_id=module_id, port=port)
                session.add(modem)
            modem.remark = item.get("remark") or port
            modem.enabled = bool(item.get("enabled", True))
        session.commit()
    finally:
        session.close()


def list_modems() -> List[Modem]:
    session = SessionLocal()
    try:
        rows = session.query(Modem).order_by(Modem.id.asc()).all()
        for row in rows:
            session.expunge(row)
        return rows
    finally:
        session.close()


def get_modem(module_id: str) -> Optional[Modem]:
    session = SessionLocal()
    try:
        modem = session.query(Modem).filter(Modem.module_id == module_id).first()
        if modem:
            session.expunge(modem)
        return modem
    finally:
        session.close()


def add_modem(port: str, remark: str) -> None:
    config = get_modem_config()
    modems = [item for item in config.get("modems", []) if item.get("port") != port]
    modems.append({"port": port, "remark": remark or port, "enabled": True})
    config["modems"] = modems
    save_modem_config(config)
    sync_config_to_db()


def update_remark(module_id: str, remark: str) -> None:
    modem = get_modem(module_id)
    if not modem:
        return
    config = get_modem_config()
    for item in config.get("modems", []):
        if item.get("port") == modem.port:
            item["remark"] = remark or modem.port
    save_modem_config(config)
    session = SessionLocal()
    try:
        row = session.query(Modem).filter(Modem.module_id == module_id).first()
        if row:
            row.remark = remark or row.port
        session.commit()
    finally:
        session.close()


def delete_modem(module_id: str) -> None:
    modem = get_modem(module_id)
    if not modem:
        return
    config = get_modem_config()
    config["modems"] = [item for item in config.get("modems", []) if item.get("port") != modem.port]
    save_modem_config(config)
    session = SessionLocal()
    try:
        row = session.query(Modem).filter(Modem.module_id == module_id).first()
        if row:
            session.delete(row)
        session.commit()
    finally:
        session.close()


def set_enabled(module_id: str, enabled: bool) -> None:
    modem = get_modem(module_id)
    if not modem:
        return
    config = get_modem_config()
    for item in config.get("modems", []):
        if item.get("port") == modem.port:
            item["enabled"] = enabled
    save_modem_config(config)
    session = SessionLocal()
    try:
        row = session.query(Modem).filter(Modem.module_id == module_id).first()
        if row:
            row.enabled = enabled
        session.commit()
    finally:
        session.close()


def update_modem_status(module_id: str, values: Dict[str, object]) -> None:
    session = SessionLocal()
    try:
        modem = session.query(Modem).filter(Modem.module_id == module_id).first()
        if not modem:
            modem = Modem(module_id=module_id, port=str(values.get("port", "")))
            session.add(modem)
        for key, value in values.items():
            if hasattr(modem, key):
                setattr(modem, key, value)
        modem.last_seen_at = values.get("last_seen_at") or now_text()
        session.commit()
    finally:
        session.close()
