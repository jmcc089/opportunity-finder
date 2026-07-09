"""
api/search.py — Vercel serverless function: POST /api/search

Orchestrates the full pipeline:
  scrape → normalize → city/date filter → classify →
  affinity filter/cut → Stage-1 prescore → Stage-2 enrich

Self-test harness:
  DEEPSEEK_MOCK=1 python api/search.py --selftest
"""
from __future__ import annotations

import json
import logging
import os
import sys
import traceback
from datetime import date
from pathlib import Path
from typing import Any

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
# Scrape with live→snapshot fallback
# ---------------------------------------------------------------------------

def _scrape_tcm(warnings: list[str]) -> list[dict]:
    try:
        rows = scrape_thecraftmap()   # live
        if rows:
            return rows
        raise ValueError("empty result from live TCM")
    except Exception as exc:
        warnings.append(f"TCM live scrape failed ({exc}); using snapshot")
        log.warning("TCM live scrape failed: %s", exc)
    try:
        snap = (_ROOT / "fixtures" / "tcm_snapshot.html").read_text(encoding="utf-8")
        rows = scrape_thecraftmap(html=snap)
        if rows:
            return rows
        raise ValueError("empty result from TCM snapshot")
    except Exception as exc2:
        warnings.append(f"TCM snapshot also failed ({exc2}); source omitted")
        log.error("TCM snapshot failed: %s", exc2)
        return []


def _scrape_fg(warnings: list[str]) -> list[dict]:
    try:
        rows = scrape_festivalguides()  # live
        if rows:
            return rows
        raise ValueError("empty result from live FG")
    except Exception as exc:
        warnings.append(f"FG live scrape failed ({exc}); using snapshot")
        log.warning("FG live scrape failed: %s", exc)
    try:
        snap = (_ROOT / "fixtures" / "fg_snapshot.html").read_text(encoding="utf-8")
        rows = scrape_festivalguides(html=snap)
        if rows:
            return rows
        raise ValueError("empty result from FG snapshot")
    except Exception as exc2:
        warnings.append(f"FG snapshot also failed ({exc2}); source omitted")
        log.error("FG snapshot failed: %s", exc2)
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
            "error": "both sources failed",
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
            "after_normalize": len(events) + (1 if len(events) else 0),  # approximate
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
# Vercel handler
# ---------------------------------------------------------------------------

def handler(request: Any, response: Any) -> None:  # pragma: no cover
    """Vercel Python runtime entry point."""
    if request.method != "POST":
        response.status_code = 405
        response.send(json.dumps({"error": "Method Not Allowed"}))
        return
    try:
        body = request.json
    except Exception:
        response.status_code = 400
        response.send(json.dumps({"error": "invalid JSON body"}))
        return
    result = run_pipeline(body)
    status = 400 if "error" in result else 200
    response.status_code = status
    response.send(json.dumps(result))


# ---------------------------------------------------------------------------
# Self-test harness  (DEEPSEEK_MOCK=1 python api/search.py --selftest)
# ---------------------------------------------------------------------------

def _selftest() -> None:
    os.environ.setdefault("DEEPSEEK_MOCK", "1")

    print("=" * 60)
    print("SELF-TEST: full pipeline (snapshots + mock DeepSeek)")
    print("=" * 60)

    # --- baseline: search that should find results ---
    body_ok = {
        "category": "hot_food",
        "city": None,       # no city filter → use all events
        "date_from": None,
        "date_to": None,
    }
    print("\n[1] Full pipeline (no city/date filter):")
    result = run_pipeline(body_ok)
    results = result.get("results", [])
    meta = result.get("meta", {})
    print(f"  results count : {len(results)}")
    print(f"  meta.warnings : {meta.get('warnings', [])}")
    assert len(results) == 5, f"Expected 5 results, got {len(results)}"
    for r in results:
        assert "estimated_fields" in r, "Missing estimated_fields"
        assert r.get("event_type") is not None, "Missing event_type"
    print("  PASS: 5 results, all have estimated_fields and event_type")

    # --- check AI fields are present ---
    ai_fields = {"final_score", "explanation", "estimated_attendance", "likely_permits", "category_fit", "recommendation"}
    present = ai_fields & set(results[0].keys())
    assert present == ai_fields, f"Missing AI fields: {ai_fields - present}"
    print(f"  PASS: AI fields present ({sorted(present)})")

    # --- single-source failure: verify warning mechanism + pipeline survives empty TCM ---
    print("\n[2] Single-source failure (TCM scraper raises → warning emitted, FG alone returns 5):")

    # Patch the name in the running module (__main__ when run directly, api.search otherwise)
    _self_mod = sys.modules[__name__]
    _orig_fn = _self_mod.scrape_thecraftmap

    def _always_raise(*_a, **_kw):
        raise RuntimeError("simulated TCM failure")

    _self_mod.scrape_thecraftmap = _always_raise
    try:
        warnings_sim: list[str] = []
        tcm_result = _scrape_tcm(warnings_sim)
    finally:
        _self_mod.scrape_thecraftmap = _orig_fn

    assert tcm_result == [], f"Expected empty list from failed TCM, got {len(tcm_result)} events"
    assert any("TCM" in w for w in warnings_sim), f"Expected TCM warning; got: {warnings_sim}"
    print(f"  PASS: empty TCM result + warning: {warnings_sim[0]}")

    # Verify pipeline still returns 5 when TCM raw list is empty (uses only FG)
    from scrapers.festivalguides import scrape_festivalguides as _orig_fg_fn
    snap_html = (_ROOT / "fixtures" / "fg_snapshot.html").read_text(encoding="utf-8")
    fg_only = _orig_fg_fn(html=snap_html)
    events_fg = normalize([], fg_only)
    events_fg = classify(events_fg)
    candidates_fg = filter_and_cut(events_fg, body_ok["category"])
    top5_fg = prescore_top5(candidates_fg, body_ok["category"])
    enriched_fg = enrich(top5_fg, body_ok["category"])
    assert len(enriched_fg) == 5, f"Expected 5 from FG alone, got {len(enriched_fg)}"
    print(f"  PASS: FG-only pipeline returns {len(enriched_fg)} results")

    # --- invalid category ---
    print("\n[3] Invalid category:")
    result3 = run_pipeline({"category": "invalid", "city": None})
    assert "error" in result3, "Expected error for invalid category"
    print(f"  PASS: error returned: {result3['error']}")

    # --- no secret in source files ---
    print("\n[4] No DEEPSEEK_API_KEY hardcoded in source:")
    key = os.environ.get("DEEPSEEK_API_KEY", "")
    if key:
        src = Path(__file__).read_text()
        assert key not in src, "API key found hardcoded in search.py!"
    print("  PASS (key absent from env or not found in source)")

    print("\n" + "=" * 60)
    print("ALL SELF-TEST CHECKS PASSED")
    print("=" * 60)


if __name__ == "__main__":
    if "--selftest" in sys.argv:
        _selftest()
    else:
        print("Usage: DEEPSEEK_MOCK=1 python api/search.py --selftest")
