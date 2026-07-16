"""
Scraper for FestivalGuides California festival list.
Courtesy note (ADR-08): FestivalGuides requests a back-link and tags noai.
We parse only public listing text for a portfolio tool; we do not reproduce
the site's editorial text wholesale.
"""
import re
import datetime
from typing import Optional

import requests
from bs4 import BeautifulSoup, Tag

_SOURCE_URL = "https://festivalguidesandreviews.com/california-festivals/"
_MONTHS = {
    "JANUARY": 1, "FEBRUARY": 2, "MARCH": 3, "APRIL": 4,
    "MAY": 5, "JUNE": 6, "JULY": 7, "AUGUST": 8,
    "SEPTEMBER": 9, "OCTOBER": 10, "NOVEMBER": 11, "DECEMBER": 12,
}
_STATUS_MARKERS = {
    "CANCELLED": "cancelled",
    "DISCONTINUED": "discontinued",
}


def _parse_date(m: int, d: int, year: int) -> str:
    return datetime.date(year, m, d).isoformat()


def _parse_date_field(date_str: str, year: int) -> tuple[str, str, bool]:
    """Return (start_iso, end_iso, date_unconfirmed) from '7/26' or '7/27-8/2' or '7/27*'."""
    date_str = date_str.strip()
    unconfirmed = date_str.endswith("*")
    date_str = date_str.rstrip("*").strip()

    range_match = re.match(r"^(\d{1,2})/(\d{1,2})-(\d{1,2})/(\d{1,2})$", date_str)
    single_match = re.match(r"^(\d{1,2})/(\d{1,2})$", date_str)

    if range_match:
        sm, sd, em, ed = (int(x) for x in range_match.groups())
        start = _parse_date(sm, sd, year)
        # Handle year-wrap edge case (Dec → Jan)
        end_year = year + 1 if em < sm else year
        end = _parse_date(em, ed, end_year)
    elif single_match:
        m2, d2 = int(single_match.group(1)), int(single_match.group(2))
        start = end = _parse_date(m2, d2, year)
    else:
        raise ValueError(f"Cannot parse date: {date_str!r}")

    return start, end, unconfirmed


def _parse_status(segments: list[str]) -> tuple[str, list[str]]:
    """Check trailing segments for status markers. Returns (status, remaining_segments)."""
    status = "active"
    clean = []
    for seg in segments:
        upper = seg.strip().upper()
        if upper in _STATUS_MARKERS:
            status = _STATUS_MARKERS[upper]
        elif upper.startswith("NEXT IN ") or upper.startswith("DISCONTINUED?"):
            status = "discontinued"
        elif upper.startswith("CANCELLED"):
            status = "cancelled"
        else:
            clean.append(seg)
    return status, clean


def _parse_entry(node_list, year: int) -> Optional[dict]:
    """
    node_list: list of BeautifulSoup nodes (NavigableString | Tag) for one <br>-line.
    Returns a raw dict or None if the line doesn't look like an event.
    """
    # Reconstruct raw text and collect hrefs
    raw_text = ""
    href = None
    for node in node_list:
        if isinstance(node, Tag) and node.name == "a":
            raw_text += node.get_text()
            if not href:
                href = node.get("href")
        else:
            raw_text += str(node) if not isinstance(node, Tag) else node.get_text()

    raw_text = raw_text.strip()
    if not raw_text:
        return None

    # Split on em-dash (–) or regular dash surrounded by spaces
    parts = [p.strip() for p in re.split(r"\s*–\s*", raw_text)]
    if len(parts) < 3:
        return None

    date_part = parts[0]
    if not re.match(r"^\d{1,2}/\d{1,2}", date_part):
        return None  # Not an event line

    # Status is the last segment if it matches a keyword; city is next-to-last after that
    status, rest = _parse_status(parts[1:])
    if len(rest) < 2:
        # Only name, no city — skip (malformed)
        return None

    name = rest[0].strip()
    city_raw = rest[-1].strip()
    # Normalize city to "City, CA"
    city = city_raw if city_raw.endswith(", CA") else f"{city_raw}, CA"

    # Parse date (may have * for unconfirmed)
    try:
        start_date, end_date, date_unconfirmed = _parse_date_field(date_part, year)
    except ValueError:
        return None

    if not name:
        return None

    return {
        "name": name,
        "city": city,
        "start_date": start_date,
        "end_date": end_date,
        "date_unconfirmed": date_unconfirmed,
        "status": status,
        "external_url": href,
        "source": "festivalguides",
    }


def scrape_festivalguides() -> list[dict]:
    """Parse the FestivalGuides California list into raw dicts.
    If html is None, fetch live (browser User-Agent)."""
    headers = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    )
}
resp = requests.get(_SOURCE_URL, headers=headers, timeout=15)
resp.raise_for_status()
html = resp.text

    today = datetime.date.today()
    current_month = today.month
    year = today.year

    soup = BeautifulSoup(html, "html.parser")
    content = (
        soup.find("div", class_="entry-content")
        or soup.find("article")
        or soup.find("main")
    )
    if not content:
        return []

    results = []
    active_month: int | None = None

    for p in content.find_all("p", class_="wp-block-paragraph"):
        text = p.get_text(strip=True)

        # Month header detection
        if text.upper() in _MONTHS:
            active_month = _MONTHS[text.upper()]
            continue

        if active_month != current_month:
            continue

        # Split paragraph into line-nodes at each <br>
        line_nodes: list = []
        for node in p.children:
            if isinstance(node, Tag) and node.name == "br":
                entry = _parse_entry(line_nodes, year)
                if entry:
                    results.append(entry)
                line_nodes = []
            else:
                line_nodes.append(node)
        # Final line after last <br> (or single-line paragraph)
        if line_nodes:
            entry = _parse_entry(line_nodes, year)
            if entry:
                results.append(entry)

    return results
