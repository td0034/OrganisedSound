from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

PID_KEYS = ["participant_id", "participantId", "participant_code", "participantCode", "pid", "code"]
SECTION_KEYS = ["section_key", "sectionKey", "section", "section_id", "sectionId", "page", "step", "form"]
TS_KEYS = [
    "updated_at", "updatedAt",
    "created_at", "createdAt",
    "timestamp", "saved_at", "savedAt", "time",
]


def parse_timestamp(record: Dict[str, Any]) -> Optional[datetime]:
    for k in TS_KEYS:
        if k in record:
            v = record.get(k)
            if isinstance(v, (int, float)):
                try:
                    return datetime.fromtimestamp(float(v))
                except Exception:
                    return None
            if isinstance(v, str):
                s = v.strip()
                if s.endswith("Z"):
                    s = s[:-1] + "+00:00"
                try:
                    return datetime.fromisoformat(s)
                except Exception:
                    pass
                for fmt in (
                    "%Y-%m-%dT%H:%M:%S.%f%z",
                    "%Y-%m-%dT%H:%M:%S%z",
                    "%Y-%m-%dT%H:%M:%S.%f",
                    "%Y-%m-%dT%H:%M:%S",
                    "%Y-%m-%d %H:%M:%S",
                ):
                    try:
                        return datetime.strptime(s, fmt)
                    except Exception:
                        pass
    return None


def _find_first(obj: Dict[str, Any], keys: List[str]) -> Optional[Any]:
    for k in keys:
        if k in obj:
            return obj.get(k)
    return None


def load_records(path: str) -> List[Dict[str, Any]]:
    in_path = Path(path)
    data = json.loads(in_path.read_text())
    if isinstance(data, dict):
        for key in ("data", "records", "rows"):
            if key in data and isinstance(data[key], list):
                data = data[key]
                break
    if not isinstance(data, list):
        raise ValueError("Input JSON must be a list of records.")

    records: List[Dict[str, Any]] = []
    for rec in data:
        if not isinstance(rec, dict):
            continue
        pid = _find_first(rec, PID_KEYS)
        section = _find_first(rec, SECTION_KEYS)
        payload = rec.get("payload") if "payload" in rec else rec.get("data") if "data" in rec else rec.get("answers")
        if not pid or not section:
            continue
        ts = parse_timestamp(rec)
        records.append({
            "participant_id": str(pid),
            "section_key": str(section),
            "payload": payload if isinstance(payload, dict) else {},
            "updated_at": ts,
            "_raw": rec,
        })

    return select_latest(records)


def select_latest(records: Iterable[Dict[str, Any]]) -> List[Dict[str, Any]]:
    latest: Dict[Tuple[str, str], Dict[str, Any]] = {}
    for rec in records:
        pid = rec.get("participant_id")
        section = rec.get("section_key")
        if not pid or not section:
            continue
        key = (pid, section)
        if key not in latest:
            latest[key] = rec
            continue
        existing = latest[key]
        t_new = rec.get("updated_at")
        t_old = existing.get("updated_at")
        if t_new and t_old:
            if t_new >= t_old:
                latest[key] = rec
        elif t_new and not t_old:
            latest[key] = rec
        else:
            # fall back to keeping the later record
            latest[key] = rec

    return list(latest.values())


def parse_order_string(order_str: Optional[str]) -> List[str]:
    if not order_str:
        return []
    return re.findall(r"[ABC]", str(order_str))
