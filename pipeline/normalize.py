"""
pipeline/normalize.py
Map raw dicts from thecraftmap and festivalguides scrapers to canonical Event shape.
"""
from __future__ import annotations

import re
from datetime import date
from typing import Any

TODAY = date.today()

OPTIONAL_FIELDS = [
    "venue", "description", "stand_cost",
    "tag_indoor", "tag_outdoor", "tag_juried",
    "deadline_date", "deadline_closed", "detail_url",
]


def _coerce_iso(val: str | None) -> str | None:
    """Accept ISO date (YYYY-MM-DD) or common variants; return ISO string or None."""
    if val is None:
        return None
    val = val.strip()
    # Already ISO
    if re.match(r"^\d{4}-\d{2}-\d{2}$", val):
        return val
    # Try M/D/YYYY or M/D/YY
    m = re.match(r"^(\d{1,2})/(\d{1,2})/(\d{2,4})$", val)
    if m:
        mo, dy, yr = int(m.group(1)), int(m.group(2)), int(m.group(3))
        yr = yr + 2000 if yr < 100 else yr
        try:
            return date(yr, mo, dy).isoformat()
        except ValueError:
            pass
    return None


def _deadline_closed(deadline_date: str | None) -> bool | None:
    if deadline_date is None:
        return None
    try:
        d = date.fromisoformat(deadline_date)
        return d < TODAY
    except ValueError:
        return None


def _estimated_fields(event: dict) -> list[str]:
    return [f for f in OPTIONAL_FIELDS if event.get(f) is None]


def _normalize_tcm(raw: dict) -> dict:
    deadline_date = _coerce_iso(raw.get("deadline_date"))
    event: dict[str, Any] = {
        "name": raw["name"],
        "city": raw["city"],
        "start_date": _coerce_iso(raw.get("start_date")),
        "end_date": _coerce_iso(raw.get("end_date")),
        "venue": raw.get("venue"),
        "description": raw.get("description"),
        "stand_cost": raw.get("stand_cost"),
        "tag_indoor": raw.get("tag_indoor"),
        "tag_outdoor": raw.get("tag_outdoor"),
        "tag_juried": raw.get("tag_juried"),
        "deadline_date": deadline_date,
        "deadline_closed": _deadline_closed(deadline_date),
        "detail_url": raw.get("detail_url"),
        "source": "thecraftmap",
        "event_type": None,
    }
    event["estimated_fields"] = _estimated_fields(event)
    return event


def _normalize_fg(raw: dict) -> dict | None:
    status = raw.get("status", "active")
    if status in ("cancelled", "discontinued"):
        return None

    desc = raw.get("description")
    if raw.get("date_unconfirmed"):
        prefix = "[date unconfirmed] "
        desc = prefix + desc if desc else prefix.strip()

    event: dict[str, Any] = {
        "name": raw["name"],
        "city": raw["city"],
        "start_date": _coerce_iso(raw.get("start_date")),
        "end_date": _coerce_iso(raw.get("end_date")),
        "venue": None,
        "description": desc if desc else None,
        "stand_cost": None,
        "tag_indoor": None,
        "tag_outdoor": None,
        "tag_juried": None,
        "deadline_date": None,
        "deadline_closed": None,
        "detail_url": raw.get("external_url"),
        "source": "festivalguides",
        "event_type": None,
    }
    event["estimated_fields"] = _estimated_fields(event)
    return event


def normalize(tcm_raw: list[dict], fg_raw: list[dict]) -> list[dict]:
    events: list[dict] = []
    for raw in tcm_raw:
        events.append(_normalize_tcm(raw))
    for raw in fg_raw:
        result = _normalize_fg(raw)
        if result is not None:
            events.append(result)
    return events
