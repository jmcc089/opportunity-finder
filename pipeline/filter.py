"""Phase 5 – Filter & rank events by vendor-category affinity."""

from __future__ import annotations

import random

AFFINITY = {
    "art_craft":    {"hot_food": 20, "drinks_desserts": 24, "souvenirs_merch": 40},
    "food":         {"hot_food": 16, "drinks_desserts": 36, "souvenirs_merch": 12},
    "music":        {"hot_food": 36, "drinks_desserts": 40, "souvenirs_merch": 38},
    "general_fair": {"hot_food": 34, "drinks_desserts": 34, "souvenirs_merch": 30},
    "cultural":     {"hot_food": 32, "drinks_desserts": 30, "souvenirs_merch": 28},
    "sports_other": {"hot_food": 30, "drinks_desserts": 34, "souvenirs_merch": 26},
}


def filter_and_cut(events: list[dict], user_category: str, cap: int = 20) -> list[dict]:
    """Drop closed-deadline events, rank the rest by affinity to user_category,
    return at most `cap` events (random tie-break at the cut)."""
    # Drop closed-deadline events
    open_events = [e for e in events if not e.get("deadline_closed")]

    # Score each event
    def score(event: dict) -> int:
        etype = event.get("event_type") or "general_fair"
        row = AFFINITY.get(etype, AFFINITY["general_fair"])
        return row.get(user_category, 0)

    # Sort descending by score
    open_events.sort(key=score, reverse=True)

    if len(open_events) <= cap:
        return open_events

    # Find score at cut boundary
    cut_score = score(open_events[cap - 1])

    # Separate definite keepers, tied group, and definite drops
    keepers = [e for e in open_events if score(e) > cut_score]
    tied = [e for e in open_events if score(e) == cut_score]

    # Random tie-break: shuffle the tied group and take what we need
    random.shuffle(tied)
    needed = cap - len(keepers)
    return keepers + tied[:needed]
