"""Phase 4: Keyword-based event type classifier."""

from __future__ import annotations

KEYWORDS: dict[str, list[str]] = {
    "general_fair": ["county fair", "state fair", "fairgrounds"],
    "cultural": ["greek", "italian", "chinese", "cultural", "heritage", "lunar", "pow wow"],
    "food": ["food", "taste", "garlic", "taco", "wine", "beer", "brew", "culinary", "bbq", "oktoberfest", "honey"],
    "music": ["music", "concert", "jazz", "bluegrass", "dj"],
    "art_craft": ["craft", "art", "artisan", "handmade", "makers", "fine art", "bead"],
    "sports_other": ["run", "marathon", "expo", "car show", "rodeo"],
}

# Priority order: index 0 = highest priority
PRIORITY = ["general_fair", "cultural", "food", "music", "art_craft", "sports_other"]

FALLBACK = "sports_other"


def classify(events: list[dict]) -> list[dict]:
    """Assign event_type to each event via keyword matching. Modifies in place."""
    for event in events:
        text = (event.get("name") or "") + " " + (event.get("description") or "")
        text_lower = text.lower()

        matched = None
        for etype in PRIORITY:
            for kw in KEYWORDS[etype]:
                if kw in text_lower:
                    matched = etype
                    break
            if matched:
                break

        event["event_type"] = matched or FALLBACK

    return events
