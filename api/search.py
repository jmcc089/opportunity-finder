"""
api/search.py — Vercel serverless function: POST /api/search

Orchestrates the full pipeline:
  scrape → normalize → city/date filter → classify →
  affinity filter/cut → Stage-1 prescore → Stage-2 enrich
"""
from __future__ import annotations

import json
import logging
import sys
from datetime import date
from pathlib import Path
from upstash_redis import Redis

# --- path setup so imports work both as a Vercel function and from project/ ---
_HERE = Path(__file__).parent          # project/api/
_ROOT = _HERE.parent                   # project/
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from scrapers.thecraftmap import scrape_thecraftmap
from scrapers.festivalguides import scrape_festivalguides
from pipeline.normalize import normalize
from pipeline.classify import classify
from pipeline.filter import filter_and_cut
from pipeline.stage1 import prescore_top5
from pipeline.stage2 import enrich

log = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

VALID_CATEGORIES = {"hot_food", "drinks_desserts", "souvenirs_merch"}

_redis = Redis.from_env()
RATE_LIMIT_MAX = 5        # max searches
RATE_LIMIT_WINDOW = 60    # per this many seconds, per IP

def _rate_limited(ip: str) -> bool:
    key = f"ratelimit:{ip}"
    count = _redis.incr(key)
    if count == 1:
        _redis.expire(key, RATE_LIMIT_WINDOW)
    return count > RATE_LIMIT_MAX

# ---------------------------------------------------------------------------
# City / date filter (step 3 of orchestration order, before classify)
# ---------------------------------------------------------------------------

def _filter_city_date(
    events: list[dict],
    city: str | None,
    date_from: str | None,
    date_to: str | None,
) -> list[dict]:
    out = []
    for ev in events:
        if city:
            ev_city = (ev.get("city") or "").lower()
            if city.lower() not in ev_city:
                continue
        sd = ev.get("start_date") or ""
        ed = ev.get("end_date") or sd
        if date_from and ed < date_from:
            continue
        if date_to and sd > date_to:
            continue
        out.append(ev)
    return out


# ---------------------------------------------------------------------------
# Scrape live sources. On failure, emit a warning and return []; the pipeline
# surfaces an honest error if both sources come back empty. No stale fallback.
# ---------------------------------------------------------------------------

def _scrape_tcm(warnings: list[str]) -> list[dict]:
    try:
        rows = scrape_thecraftmap()
        if rows:
            return rows
        raise ValueError("empty result from live TCM")
    except Exception as exc:
        warnings.append(f"TCM scrape failed ({exc})")
        log.warning("TCM scrape failed: %s", exc)
        return []


def _scrape_fg(warnings: list[str]) -> list[dict]:
    try:
        rows = scrape_festivalguides()
        if rows:
            return rows
        raise ValueError("empty result from live FG")
    except Exception as exc:
        warnings.append(f"FG scrape failed ({exc})")
        log.warning("FG scrape failed: %s", exc)
        return []


# ---------------------------------------------------------------------------
# Core pipeline
# ---------------------------------------------------------------------------

def run_pipeline(body: dict) -> dict:
    """
    body keys: category, city, date_from, date_to, permits_held (optional)
    Returns {"results": [...], "meta": {...}}
    """
    category = body.get("category", "")
    if category not in VALID_CATEGORIES:
        return {"error": f"invalid category '{category}'; must be one of {sorted(VALID_CATEGORIES)}"}

    city = body.get("city") or None
    date_from = body.get("date_from") or None
    date_to = body.get("date_to") or None

    warnings: list[str] = []

    # 1. Scrape
    tcm_raw = _scrape_tcm(warnings)
    fg_raw = _scrape_fg(warnings)

    if not tcm_raw and not fg_raw:
        return {
            "error": "could not fetch events right now; please try again in a moment",
            "meta": {"warnings": warnings},
        }

    # 2. Normalize
    events = normalize(tcm_raw, fg_raw)

    # 3. City / date filter, then classify
    events = _filter_city_date(events, city, date_from, date_to)
    events = classify(events)

    # 4. Affinity filter + cut to ≤20
    candidates = filter_and_cut(events, category)

    if not candidates:
        return {
            "results": [],
            "meta": {
                "warnings": warnings,
                "note": "no events matched the search criteria after filtering",
            },
        }

    # 5. Stage-1 pre-score → top 5
    top5 = prescore_top5(candidates, category)

    # 6. Stage-2 enrich
    enriched = enrich(top5, category)

    return {
        "results": enriched,
        "meta": {
            "total_scraped": len(tcm_raw) + len(fg_raw),
            "after_city_date_filter": len(events),
            "after_affinity_cut": len(candidates),
            "returned": len(enriched),
            "warnings": warnings,
            "sources_used": (
                (["thecraftmap"] if tcm_raw else []) +
                (["festivalguides"] if fg_raw else [])
            ),
            "generated_at": date.today().isoformat(),
        },
    }


# ---------------------------------------------------------------------------
# Flask app — Vercel Python runtime entry point
# ---------------------------------------------------------------------------

from flask import Flask, request as flask_request, Response  # noqa: E402

app = Flask(__name__)


@app.route("/api/search", methods=["POST"])
def search() -> Response:
    ip = flask_request.headers.get("x-forwarded-for", flask_request.remote_addr or "unknown").split(",")[0].strip()
    if _rate_limited(ip):
        return Response(
            json.dumps({"error": "too many requests, please wait a minute and try again"}),
            status=429,
            mimetype="application/json",
        )
    try:
        body = flask_request.get_json(force=True) or {}
    except Exception:
        return Response(json.dumps({"error": "invalid JSON body"}), status=400, mimetype="application/json")
    result = run_pipeline(body)
    status = 400 if "error" in result else 200
    return Response(json.dumps(result), status=status, mimetype="application/json")
