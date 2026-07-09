"""
Stage-1: cheap DeepSeek pre-score → top 5 candidates.

Sends ≤20 events to DeepSeek with Prompt-1 (score only, 0-100).
Returns top 5 sorted by score descending.
Falls back to affinity order on any parse failure.
"""
import json
import logging
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from llm.deepseek import call_deepseek

log = logging.getLogger(__name__)

AFFINITY = {
    "art_craft":    {"hot_food": 20, "drinks_desserts": 24, "souvenirs_merch": 40},
    "food":         {"hot_food": 16, "drinks_desserts": 36, "souvenirs_merch": 12},
    "music":        {"hot_food": 36, "drinks_desserts": 40, "souvenirs_merch": 38},
    "general_fair": {"hot_food": 34, "drinks_desserts": 34, "souvenirs_merch": 30},
    "cultural":     {"hot_food": 32, "drinks_desserts": 30, "souvenirs_merch": 28},
    "sports_other": {"hot_food": 30, "drinks_desserts": 34, "souvenirs_merch": 26},
}

SYSTEM_MESSAGE = "You output only JSON. No explanation. No markdown. No code fences."

PROMPT_TEMPLATE = """\
You are scoring California events for a mobile vendor deciding which to attend.

Vendor category: {user_category}

Score each event 0-100 for how well it fits the vendor category.
Base scoring on two factors only:
1. Affinity: how well the event type matches the vendor category (use the table below).
2. Saturation: if the vendor's category exactly matches the event (e.g. food truck at a food festival), score lower due to competition saturation (reduce by 10-20 points).

Affinity table (event_type × category → affinity score out of 40):
art_craft:    hot_food=20, drinks_desserts=24, souvenirs_merch=40
food:         hot_food=16, drinks_desserts=36, souvenirs_merch=12
music:        hot_food=36, drinks_desserts=40, souvenirs_merch=38
general_fair: hot_food=34, drinks_desserts=34, souvenirs_merch=30
cultural:     hot_food=32, drinks_desserts=30, souvenirs_merch=28
sports_other: hot_food=30, drinks_desserts=34, souvenirs_merch=26

Events to score:
{events_json}

Return ONLY a JSON array with one object per event, in any order:
[{{"id": <int>, "score": <int 0-100>}}, ...]
"""


def _affinity_order(candidates: list[dict], user_category: str) -> list[dict]:
    def key(e):
        et = e.get("event_type", "sports_other") or "sports_other"
        return AFFINITY.get(et, {}).get(user_category, 0)
    return sorted(candidates, key=key, reverse=True)


def prescore_top5(candidates: list[dict], user_category: str) -> list[dict]:
    """Score ≤20 candidates with DeepSeek Prompt-1; return top 5 by score."""
    # Assign stable ids
    indexed = [dict(e, _stage1_id=i) for i, e in enumerate(candidates)]

    events_for_prompt = [
        {"id": e["_stage1_id"], "name": e["name"], "event_type": e.get("event_type"), "city": e.get("city")}
        for e in indexed
    ]

    prompt = PROMPT_TEMPLATE.format(
        user_category=user_category,
        events_json=json.dumps(events_for_prompt, indent=2),
    )

    messages = [
        {"role": "system", "content": SYSTEM_MESSAGE},
        {"role": "user", "content": prompt},
    ]

    raw = call_deepseek(messages, max_tokens=256)

    # Parse defensively
    scores_by_id: dict[int, int] = {}
    try:
        text = raw.strip()
        # Strip stray fences
        if text.startswith("```"):
            lines = text.splitlines()
            text = "\n".join(l for l in lines if not l.startswith("```"))
        parsed = json.loads(text)
        for item in parsed:
            scores_by_id[int(item["id"])] = int(item["score"])
    except Exception as exc:
        log.warning("Stage-1 JSON parse failed (%s); falling back to affinity order", exc)
        fallback = _affinity_order(candidates, user_category)
        return fallback[:5]

    # Attach scores
    for e in indexed:
        sid = e["_stage1_id"]
        e["_stage1_score"] = scores_by_id.get(sid, 0)

    sorted_events = sorted(indexed, key=lambda e: e["_stage1_score"], reverse=True)
    return sorted_events[:5]
