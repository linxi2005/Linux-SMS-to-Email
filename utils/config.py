import json
import os
from pathlib import Path
from typing import Any, Dict

ROOT_DIR = Path(__file__).resolve().parents[1]
CONFIG_DIR = ROOT_DIR / "config"
DATA_DIR = ROOT_DIR / "data"
LOG_DIR = DATA_DIR / "log"
BACKUP_DIR = DATA_DIR / "backup"


def ensure_runtime_dirs() -> None:
    for path in (CONFIG_DIR, DATA_DIR, LOG_DIR, BACKUP_DIR):
        path.mkdir(parents=True, exist_ok=True)


def load_json(path: Path, default: Dict[str, Any]) -> Dict[str, Any]:
    ensure_runtime_dirs()
    if not path.exists():
        save_json(path, default, secure=path.name in {"mail.json", "config.json", "modem_config.json"})
        return dict(default)
    try:
        with path.open("r", encoding="utf-8") as file_obj:
            data = json.load(file_obj)
        if isinstance(data, dict):
            merged = dict(default)
            merged.update(data)
            return merged
    except (OSError, json.JSONDecodeError):
        pass
    return dict(default)


def save_json(path: Path, data: Dict[str, Any], secure: bool = False) -> None:
    ensure_runtime_dirs()
    temp_path = path.with_suffix(path.suffix + ".tmp")
    with temp_path.open("w", encoding="utf-8") as file_obj:
        json.dump(data, file_obj, ensure_ascii=False, indent=2)
        file_obj.write("\n")
    os.replace(str(temp_path), str(path))
    if secure:
        try:
            os.chmod(path, 0o600)
        except OSError:
            pass


def get_app_config() -> Dict[str, Any]:
    defaults = {
        "app_name": "EC20 SMS Forwarder",
        "version": "1.0.0",
        "host": "0.0.0.0",
        "port": 5000,
        "secret_key": "change-this-secret-key",
        "admin_username": "admin",
        "admin_password_hash": "",
        "session_timeout_minutes": 60,
        "log_level": "INFO",
        "sms_page_size": 20,
        "sync_interval_seconds": 30,
        "heartbeat_interval_seconds": 120,
        "reconnect_initial_seconds": 30,
        "reconnect_max_seconds": 600,
        "mail_timeout_seconds": 20,
        "ui_refresh_seconds": 20,
    }
    return load_json(CONFIG_DIR / "config.json", defaults)


def save_app_config(config: Dict[str, Any]) -> None:
    save_json(CONFIG_DIR / "config.json", config, secure=True)


def get_mail_config() -> Dict[str, Any]:
    defaults = {
        "enabled": False,
        "smtp_server": "",
        "port": 465,
        "use_ssl": True,
        "use_tls": False,
        "username": "",
        "from_email": "",
        "password": "",
        "recipients": [],
        "subject_template": "收到来自{{phone}}的新短信",
        "body_template": "来源号码：{{phone}}\n接收时间：{{time}}\n短信内容：{{content}}",
        "timeout_seconds": 20,
    }
    return load_json(CONFIG_DIR / "mail.json", defaults)


def save_mail_config(config: Dict[str, Any]) -> None:
    save_json(CONFIG_DIR / "mail.json", config, secure=True)


def get_modem_config() -> Dict[str, Any]:
    return load_json(CONFIG_DIR / "modem_config.json", {"modems": []})


def save_modem_config(config: Dict[str, Any]) -> None:
    if "modems" not in config or not isinstance(config["modems"], list):
        config["modems"] = []
    save_json(CONFIG_DIR / "modem_config.json", config, secure=True)
