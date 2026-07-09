# Opportunity Finder — California Events

A web app for mobile businesses (food trucks, drink/dessert carts, souvenir vendors) to find California events worth setting up at. The user fills a form; the backend scrapes two live sources, filters and scores in a token-controlled cascade, and returns the top 5 events with a score, a plain-language verdict, and a mix of real and AI-estimated fields — visually flagged in the UI.

**Live:** https://opportunity-finder-ca.vercel.app

---

## The problem

Mobile vendors don't have a fast way to evaluate which events are worth the cost of attending. Event details are scattered across multiple listing sites, and assessing fit — by category, city, permits, expected attendance, stand cost — takes manual research per event.

## How it works

```
Scraping          Python filter          Stage-1 DeepSeek      Stage-2 DeepSeek
─────────         ─────────────          ────────────────       ────────────────
~50 TCM +    →   drop closed        →   cheap pre-score    →   final rich query
current-mo FG    deadline; rank by       ~20 → top 5            on the 5 →
                 affinity; cut to 20     by score               shown to user
```

Each stage narrows the field to control token cost. Nothing hits the LLM until Python has cheaply cut the field to ~20 events.

## Stack

| Layer | Tool | Purpose |
|---|---|---|
| Scraping | Python / BeautifulSoup | TheCraftMap + FestivalGuides live + snapshot fallback |
| Pipeline | Python (classify, filter, normalize) | Event typing, affinity scoring, deadline filtering |
| AI | DeepSeek `deepseek-v4-flash` | 2-stage scoring: pre-score → enrichment |
| API | Flask (Vercel serverless) | `/api/search` endpoint orchestrating the full cascade |
| Frontend | React + Vite + TypeScript + Tailwind | Form + result cards with real-vs-AI field markers |
| Deploy | Vercel | Python functions + static frontend, single project |

## Key design decisions

- **No database.** Events are scraped live on each request with a snapshot fallback. Portfolio use case, low traffic — no persistence needed.
- **Two-stage LLM cascade.** Stage 1 (pre-score 20 events cheaply) → Stage 2 (enrich top 5 richly). Controls token cost without sacrificing result quality.
- **Real vs. AI field markers.** Fields that come from scraping show ✓; fields estimated by DeepSeek show ✦. The distinction is visible on every result card.
- **Affinity table over embeddings.** A hand-tuned 3×6 matrix (category × event type) ranks events deterministically before the LLM sees them. Fast, auditable, no vector infrastructure.

## Project structure

```
project/
├── api/search.py          # Flask entrypoint — orchestrates full cascade
├── scrapers/
│   ├── thecraftmap.py     # TheCraftMap scraper + snapshot fallback
│   └── festivalguides.py  # FestivalGuides scraper + snapshot fallback
├── pipeline/
│   ├── normalize.py       # Raw dicts → Event objects
│   ├── classify.py        # Keyword-based event_type assignment
│   └── filter.py          # Deadline drop + affinity rank + cut to 20
├── llm/
│   ├── deepseek.py        # DeepSeek client (mock-capable)
│   ├── stage1.py          # Pre-score 20 → top 5
│   └── stage2.py          # Enrich top 5 → final output
├── frontend/              # Vite + React + TypeScript app
│   └── src/
│       ├── App.tsx
│       ├── components/SearchForm.tsx
│       ├── components/ResultCard.tsx
│       └── components/FieldRow.tsx
└── fixtures/              # Sample data for offline dev/testing
```

## Local dev

```bash
cd project
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# Run API in mock mode (no DeepSeek key needed)
DEEPSEEK_MOCK=1 python api/search.py --selftest

# Run frontend
cd frontend && npm install && npm run dev
```

Set `DEEPSEEK_API_KEY` in `.env.local` for live DeepSeek calls.
