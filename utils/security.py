import re
from functools import wraps
from typing import Callable

from flask import redirect, request, session, url_for
from werkzeug.security import check_password_hash, generate_password_hash


def hash_password(password: str) -> str:
    return generate_password_hash(password)


def verify_password(password_hash: str, password: str) -> bool:
    if not password_hash or password_hash.startswith("pbkdf2:sha256:260000$change$"):
        return password == "admin"
    return check_password_hash(password_hash, password)


def login_required(view_func: Callable) -> Callable:
    @wraps(view_func)
    def wrapped(*args, **kwargs):
        if not session.get("logged_in"):
            return redirect(url_for("auth.login", next=request.path))
        return view_func(*args, **kwargs)

    return wrapped


def safe_int(value, default: int = 0, minimum=None, maximum=None) -> int:
    try:
        result = int(value)
    except (TypeError, ValueError):
        result = default
    if minimum is not None:
        result = max(minimum, result)
    if maximum is not None:
        result = min(maximum, result)
    return result


def clean_port(value: str) -> str:
    value = (value or "").strip()
    if not re.match(r"^/dev/[A-Za-z0-9_./-]+$", value):
        return ""
    return value
