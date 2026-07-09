import pathlib
import re
from datetime import datetime

import requests
from bs4 import BeautifulSoup

SNAPSHOT = pathlib.Path(__file__).parent.parent / "fixtures" / "tcm_snapshot.html"
SOURCE_URL = "https://www.thecraftmap.com/fairs/california"
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/125.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml",
    "Accept-Language": "en-US,en;q=0.9",
}

MONTH_MAP = {
    "jan": 1, "feb": 2, "mar": 3, "apr": 4, "may": 5, "jun": 6,
    "jul": 7, "aug": 8, "sep": 9, "oct": 10, "nov": 11, "dec": 12,
}

DATE_RE = re.compile(
    r"(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\.?\s+\d{1,2}(?:,?\s+\d{4})?",
    re.IGNORECASE,
)


def _parse_date(token: str) -> str | None:
    token = token.strip().rstrip(",")
    m = re.match(r"(\w+)\s+(\d{1,2})(?:,?\s+(\d{4}))?", token)
    if not m:
        return None
    month_str = m.group(1)[:3].lower()
    day = int(m.group(2))
    year = int(m.group(3)) if m.group(3) else datetime.now().year
    month = MONTH_MAP.get(month_str)
    if not month:
        return None
    try:
        return datetime(year, month, day).strftime("%Y-%m-%d")
    except ValueError:
        return None


def _parse_date_field(raw: str) -> tuple[str | None, str | None]:
    """Parse a raw date string (single or range) into (start_date, end_date) ISO."""
    raw = raw.strip()
    # Split on dash/en-dash with optional spaces
    parts = re.split(r"\s*[-–—]\s*", raw)
    if len(parts) == 2:
        start = _parse_date(parts[0])
        end = _parse_date(parts[1])
        return start, end
    d = _parse_date(raw)
    return d, d


def _parse_city(text: str) -> str:
    text = text.strip()
    if not re.search(r",\s*CA$", text, re.I):
        text = text.rstrip(",") + ", CA"
    return text


def _get_deadline_map(soup: BeautifulSoup) -> tuple[dict[str, str], set[str]]:
    """Build ({fair_slug_href: deadline_date}, {deadline-only hrefs}) from the
    'Upcoming Deadlines' section.  The second set contains hrefs that appear
    ONLY in the deadline block and not in the main listing — they should be
    excluded from the event output.
    """
    deadlines: dict[str, str] = {}
    deadline_hrefs: set[str] = set()

    # Find a section / div that contains "deadline" in heading text
    for heading in soup.find_all(re.compile(r"^h[1-6]$")):
        if "deadline" in heading.get_text(separator=" ").lower():
            container = heading.find_parent()
            if container:
                for a in container.find_all("a", href=re.compile(r"^/fair/")):
                    href = a["href"]
                    deadline_hrefs.add(href)
                    parent_text = a.parent.get_text(separator=" ") if a.parent else ""
                    dm = DATE_RE.search(parent_text)
                    if dm:
                        d = _parse_date(dm.group())
                        if d:
                            deadlines[href] = d
            break
    return deadlines, deadline_hrefs


def scrape_thecraftmap(html: str | None = None) -> list[dict]:
    """Parse TheCraftMap California listing into raw dicts.

    If html is None, fetch live (with a browser User-Agent).  On any network
    error, fall back to the saved snapshot at fixtures/tcm_snapshot.html.
    Passing html directly skips the network entirely.
    """
    if html is None:
        try:
            resp = requests.get(SOURCE_URL, headers=HEADERS, timeout=20)
            if resp.status_code != 200:
                raise ValueError(f"HTTP {resp.status_code}")
            html = resp.text
            # Refresh snapshot on successful fetch
            SNAPSHOT.write_text(html, encoding="utf-8")
        except Exception:
            html = SNAPSHOT.read_text(encoding="utf-8")

    soup = BeautifulSoup(html, "html.parser")
    deadline_map, deadline_only_hrefs = _get_deadline_map(soup)

    events: list[dict] = []
    seen_urls: set[str] = set()

    for a in soup.find_all("a", href=re.compile(r"^/fair/")):
        href = a["href"]
        if href in seen_urls:
            continue
        seen_urls.add(href)

        detail_url = f"https://www.thecraftmap.com{href}"

        # Skip events that only appear in the deadline block (no main listing card)
        if href in deadline_only_hrefs:
            continue

        # Require the anchor text to contain the 📅 emoji — deadline-only entries
        # lack it and would produce incomplete records
        raw_text_full = a.get_text(separator=" | ", strip=True)
        if "📅" not in raw_text_full:
            continue

        # Split text on ' | ' separator that the page uses between span elements
        parts = [p.strip() for p in raw_text_full.split(" | ")]
        parts = [p for p in parts if p]  # drop empty

        # --- Extract fields using emoji markers as positional anchors ---
        date_raw = city_raw = venue_raw = description_raw = stand_cost_raw = None
        name = None
        tag_indoor = tag_outdoor = tag_juried = False

        i = 0
        while i < len(parts):
            tok = parts[i]
            if tok == "📅" and i + 1 < len(parts):
                # Take only the FIRST date token; subsequent 📅 are urgency labels
                if date_raw is None:
                    date_raw = parts[i + 1]
                i += 2
            elif tok == "📍" and i + 1 < len(parts):
                city_raw = parts[i + 1]
                i += 2
                # Next part might be '•' + venue
                if i < len(parts) and parts[i] == "•" and i + 1 < len(parts):
                    venue_raw = parts[i + 1]
                    i += 2
            elif tok == "💰" and i + 1 < len(parts):
                stand_cost_raw = parts[i + 1]
                i += 2
            elif "indoor" in tok.lower() or "🏠" in tok:
                tag_indoor = True
                i += 1
            elif "outdoor" in tok.lower() or "🌳" in tok:
                tag_outdoor = True
                i += 1
            elif "juried" in tok.lower() or "⭐" in tok:
                tag_juried = True
                i += 1
            elif tok in ("⏰",):
                i += 2  # skip urgency token + its value
            else:
                # Likely the event name (longest non-marker token before city)
                if name is None and city_raw is None and not re.match(r"^[📅📍💰⭐🏠🌳⏰]", tok):
                    # Heuristic: name is the longest "plain text" token seen so far
                    if len(tok) > 3 and not re.match(r"^\d", tok):
                        name = tok
                elif name is not None and city_raw is not None:
                    # Anything after city/venue is description
                    if description_raw is None:
                        description_raw = tok
                i += 1

        # Also scan for inline badge text (e.g. "💰 $285" merged into one token)
        full_text = a.get_text(separator=" ", strip=True)
        if stand_cost_raw is None:
            cm = re.search(r"💰\s*(\$[\d,]+(?:\s*[-–]\s*\$[\d,]+)?)", full_text)
            if cm:
                stand_cost_raw = cm.group(1)
        if not tag_indoor:
            tag_indoor = bool(re.search(r"🏠|indoor", full_text, re.I))
        if not tag_outdoor:
            tag_outdoor = bool(re.search(r"🌳|outdoor", full_text, re.I))
        if not tag_juried:
            tag_juried = bool(re.search(r"⭐|juried", full_text, re.I))

        # Fallback: derive name from href slug if still missing
        if not name:
            slug = href.split("/fair/")[-1]
            name = slug.replace("-", " ").title()

        start_date, end_date = _parse_date_field(date_raw) if date_raw else (None, None)
        city = _parse_city(city_raw) if city_raw else None
        deadline_date = deadline_map.get(href)

        events.append({
            "name": name,
            "city": city,
            "start_date": start_date,
            "end_date": end_date,
            "venue": venue_raw,
            "description": description_raw,
            "stand_cost": stand_cost_raw,
            "tag_indoor": tag_indoor,
            "tag_outdoor": tag_outdoor,
            "tag_juried": tag_juried,
            "deadline_date": deadline_date,
            "detail_url": detail_url,
            "source": "thecraftmap",
        })

    return events
