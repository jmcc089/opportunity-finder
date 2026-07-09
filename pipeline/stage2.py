"""
Stage-2: DeepSeek final enrichment on the top-5 candidates.

One batched call with Prompt-2 returning 6 AI fields per event.
AI fields are appended to each event's estimated_fields list.
Falls back to neutral placeholder results on any parse failure.
"""
import json
import logging
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from llm.deepseek import call_deepseek

log = logging.getLogger(__name__)

SYSTEM_MESSAGE = "You output only JSON. No explanation outside the JSON."

PROMPT_TEMPLATE = """\
You are advising California mobile vendors (food trucks, carts, souvenir sellers) \
on which events are worth attending.

Vendor category: {user_category}

Below are 5 candidate events. For each, return a JSON object with exactly these fields:
- final_score: integer 0-100, fit for the vendor's category
- explanation: plain language reason, ≤40 words
- estimated_attendance: short string (e.g. "~15,000")
- likely_permits: array of ≤3 short permit names needed at the county level for this \
vendor category (keep generic and verifiable; omit specifics you cannot confirm)
- category_fit: one of "good_fit" or "saturated"
- recommendation: one of "worth_it", "with_reservations", or "better_not"

Events (id is index 0-4):
{events_json}

Return ONLY a JSON array of 5 objects, each with the key "id" (matching the event index) \
plus the 6 fields above. No prose, no markdown, no code fences.
"""

_AI_FIELDS = ["final_score", "explanation", "estimated_attendance", "likely_permits", "category_fit", "recommendation"]

_NEUTRAL_RESULT = {
    "final_score": 50,
    "explanation": "Score unavailable; enrichment failed.",
    "estimated_attendance": "unknown",
    "likely_permits": [],
    "category_fit": "good_fit",
    "recommendation": "with_reservations",
}


def enrich(top5: list[dict], user_category: str) -> list[dict]:
    """One DeepSeek call with Prompt-2 over the 5 events.

    Merges AI fields onto each event's real fields and appends every AI field
    name to estimated_fields. Returns a list of 5 result dicts for the frontend.
    """
    indexed = [dict(e) for e in top5]

    events_for_prompt = []
    for i, e in enumerate(indexed):
        events_for_prompt.append({
            "id": i,
            "name": e.get("name"),
            "city": e.get("city"),
            "start_date": e.get("start_date"),
            "end_date": e.get("end_date"),
            "venue": e.get("venue"),
            "stand_cost": e.get("stand_cost"),
            "tag_indoor": e.get("tag_indoor"),
            "tag_outdoor": e.get("tag_outdoor"),
            "tag_juried": e.get("tag_juried"),
            "deadline_date": e.get("deadline_date"),
            "source": e.get("source"),
            "detail_url": e.get("detail_url"),
            "event_type": e.get("event_type"),
            "estimated_fields": e.get("estimated_fields", []),
        })

    prompt = PROMPT_TEMPLATE.format(
        user_category=user_category,
        events_json=json.dumps(events_for_prompt, indent=2),
    )

    messages = [
        {"role": "system", "content": SYSTEM_MESSAGE},
        {"role": "user", "content": prompt},
    ]

    raw = call_deepseek(messages, max_tokens=1024, mock_fixture="mock_stage2_response.json")

    ai_by_id: dict[int, dict] = {}
    try:
        text = raw.strip()
        if text.startswith("```"):
            lines = text.splitlines()
            text = "\n".join(l for l in lines if not l.startswith("```"))
        parsed = json.loads(text)
        for item in parsed:
            ai_by_id[int(item["id"])] = item
    except Exception as exc:
        log.warning("Stage-2 JSON parse failed (%s); using neutral placeholders", exc)

    results = []
    for i, event in enumerate(indexed):
        ai = ai_by_id.get(i, {})
        merged = dict(event)

        # Merge AI fields (never overwrite real scraped fields)
        for field in _AI_FIELDS:
            merged[field] = ai.get(field, _NEUTRAL_RESULT[field])

        # Append AI field names to estimated_fields
        existing = list(merged.get("estimated_fields") or [])
        for field in _AI_FIELDS:
            if field not in existing:
                existing.append(field)
        merged["estimated_fields"] = existing

        results.append(merged)

    return results
