import re
from datetime import datetime
from typing import Dict, List, Optional

CMTI_RE = re.compile(r'\+CMTI:\s*"(?P<storage>[^"]+)",\s*(?P<index>\d+)', re.I)
CMGR_RE = re.compile(r'\+CMGR:\s*"(?P<status>[^"]*)"\s*,\s*"(?P<phone>[^"]*)"\s*,\s*"(?P<alpha>[^"]*)"\s*,\s*"(?P<time>[^"]*)"', re.I)
CMGL_RE = re.compile(r'\+CMGL:\s*(?P<index>\d+)\s*,\s*"(?P<status>[^"]*)"\s*,\s*"(?P<phone>[^"]*)"\s*,\s*"(?P<alpha>[^"]*)"\s*,\s*"(?P<time>[^"]*)"', re.I)


def parse_cmti(line: str) -> Optional[Dict[str, object]]:
    match = CMTI_RE.search(line or "")
    if not match:
        return None
    return {"storage": match.group("storage"), "index": int(match.group("index"))}


def is_ucs2_hex(value: str) -> bool:
    text = (value or "").strip()
    if len(text) < 4 or len(text) % 4 != 0:
        return False
    if not re.fullmatch(r"[0-9A-Fa-f]+", text):
        return False
    try:
        decoded = bytes.fromhex(text).decode("utf-16-be")
    except (ValueError, UnicodeDecodeError):
        return False
    return bool(decoded.strip())


def decode_sms_text(value: str) -> Dict[str, str]:
    text = (value or "").strip()
    if is_ucs2_hex(text):
        return {"content": bytes.fromhex(text).decode("utf-16-be"), "encoding": "UCS2"}
    return {"content": text, "encoding": "UTF-8"}


def normalize_time(value: str) -> str:
    value = (value or "").strip()
    for fmt in ("%y/%m/%d,%H:%M:%S%z", "%y/%m/%d,%H:%M:%S"):
        try:
            return datetime.strptime(value.replace("+32", "+0800"), fmt).strftime("%Y-%m-%d %H:%M:%S")
        except ValueError:
            continue
    return value or datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def parse_cmgr(response: str, sms_index: int = None, storage: str = "") -> Optional[Dict[str, object]]:
    lines = [line.strip() for line in (response or "").splitlines() if line.strip()]
    header_index = None
    header_match = None
    for index, line in enumerate(lines):
        match = CMGR_RE.search(line)
        if match:
            header_index = index
            header_match = match
            break
    if header_match is None or header_index is None:
        return None
    content_line = ""
    if header_index + 1 < len(lines):
        content_line = lines[header_index + 1]
    decoded = decode_sms_text(content_line)
    status = header_match.group("status")
    return {
        "sms_index": sms_index,
        "storage": storage,
        "phone": header_match.group("phone"),
        "receive_time": normalize_time(header_match.group("time")),
        "content": decoded["content"],
        "encoding": decoded["encoding"],
        "is_read": "REC READ" in status.upper(),
    }


def parse_cmgl(response: str, storage: str = "") -> List[Dict[str, object]]:
    lines = [line.strip() for line in (response or "").splitlines() if line.strip()]
    results = []
    index = 0
    while index < len(lines):
        match = CMGL_RE.search(lines[index])
        if not match:
            index += 1
            continue
        content_line = lines[index + 1] if index + 1 < len(lines) else ""
        decoded = decode_sms_text(content_line)
        status = match.group("status")
        results.append(
            {
                "sms_index": int(match.group("index")),
                "storage": storage,
                "phone": match.group("phone"),
                "receive_time": normalize_time(match.group("time")),
                "content": decoded["content"],
                "encoding": decoded["encoding"],
                "is_read": "REC READ" in status.upper(),
                "status": status,
            }
        )
        index += 2
    return results


def parse_csq(response: str) -> Dict[str, object]:
    match = re.search(r"\+CSQ:\s*(\d+)\s*,\s*(\d+)", response or "")
    if not match:
        return {"signal_raw": "", "signal_percent": 0}
    rssi = int(match.group(1))
    if rssi == 99:
        percent = 0
    else:
        percent = max(0, min(100, int(rssi / 31 * 100)))
    return {"signal_raw": "{},{}".format(match.group(1), match.group(2)), "signal_percent": percent}
