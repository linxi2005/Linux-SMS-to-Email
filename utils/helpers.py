from datetime import datetime


def now_text() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def yes_no(value: bool) -> str:
    return "是" if value else "否"
