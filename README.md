> A web app that scrapes two California event listing sites, normalizes them into a single event object, and returns the five best-fit events for a given vendor category. Both sources are written for human skimming: TheCraftMap embeds cost and tags in text with deadlines on a separate part of the page, FestivalGuides is a plain-text list where the city is whatever follows the last dash. Neither is queryable by vendor fit. The pipeline classifies event types by keyword, ranks by a hand-tuned affinity table, and cuts the field to twenty before any model call, then runs a two-stage DeepSeek cascade: a cheap numeric pre-score on the twenty, rich enrichment on the surviving five. Each field on a result card is marked as scraped or AI-estimated.

**Live:** https://opportunity-finder-ca.vercel.app

---

# 1. The Problem

Mobile vendors decide where to set up: food trucks selling hot food, carts selling drinks and desserts, sellers offering souvenirs and merch. A stand fee ranges from nothing to a few hundred dollars, events run one to three days, and application deadlines close weeks ahead of the event date. A wrong choice costs a wasted weekend and the fee.

Two public sources cover California, and neither is built to be queried. TheCraftMap serves around fifty events at a time with the richest fields available: name, city, date range, venue, description, stand cost, and tags for indoor, outdoor, and juried. Application deadlines are listed, but in a separate section rather than on the event itself. FestivalGuides covers the current month as plain text, one line per event, formatted as date, name, city, with an asterisk marking unconfirmed dates and words like CANCELLED appended at the end of the line. Its value is coverage of food festivals that TheCraftMap does not carry.

Neither source is queryable by vendor category. There is no field for fit, no way to filter for events where a category has an audience rather than six competitors already booked, and no indication of whether the deadline has already passed. The sites are indexes. Producing a ranked answer from them takes real work: normalizing two different formats into one shape, assigning an event type the sources do not provide, deciding fit before spending tokens on fifty events, and tracking which fields on the final answer came from a page and which came from a model.

---

# 2. System Design

This is a scoped MVP built, not a production deployment at scale. The design goal is narrow: turn two unstructured event indexes into a ranked, honest answer for one vendor category, spending as few model tokens as possible and never presenting a guess as a confirmed fact. Everything below follows from that one goal. The requirements set the boundary, the architecture decisions record the trade-offs that got made and the ones that got rejected, and the scope names what was left out on purpose.

## 2.1 Requirements

### Functional

- Scrape [TheCraftMap](http://thecraftmap.com/fairs/california) and [FestivalGuides](http://festivalguidesandreviews.com/california-festivals/) live on each request.
- Normalize both formats into a single event object, tracking which fields came back empty.
- Assign an event type the sources do not provide.
- Filter by city and date range, and drop events whose application deadline has passed.
- Rank by vendor category against event type, deterministically, before any model call.
- Run a two-stage model cascade: a cheap numeric pre-score on roughly twenty candidates, then rich enrichment on the surviving five.
- Return five results with score, explanation, estimated attendance, permit guidance, and stand cost, with each field marked as scraped or estimated.

### Non-functional and hard rules

- **No database.** Nothing about an event is persisted. The only stored state is an ephemeral per-IP counter for rate limiting, which expires after sixty seconds.
- **Nothing reaches the model unfiltered.** No event is sent to the LLM before the deterministic filter has capped the candidate set at roughly twenty.
- **Fail honestly.** A source that cannot be reached contributes nothing and is named in `meta.warnings`, and the request still answers from the surviving source. If both sources fail, the request returns an error rather than stale data. There is no snapshot, no cache, and no silent fallback.
- **Degrade, do not crash, on model failure.** A Stage 1 parse failure falls back to the deterministic affinity order. A Stage 2 parse failure returns neutral placeholders. A bad model response costs result quality, never the request itself.
- **The public endpoint is rate limited** to five searches per minute per IP.
- **Permit guidance is category level, not county level**, and carries a disclaimer that it is not legal advice.
- **Single Vercel project:** Python serverless functions and a static React frontend, with no separate services.

---

## 2.2 The Event Object

Every phase from normalization onward passes this one shape. The scrapers produce two different raw formats; `normalize` maps both onto this contract, and each later phase only adds to it. Nothing downstream has to know which source an event came from.

| Field | Type | Origin |
|---|---|---|
| `name`, `city` | str | Scraped, required |
| `start_date`, `end_date` | str \| null | Scraped, coerced to ISO |
| `venue`, `description`, `stand_cost` | str \| null | Scraped when present |
| `tag_indoor`, `tag_outdoor`, `tag_juried` | bool \| null | Scraped (TheCraftMap only) |
| `deadline_date` | str \| null | Scraped, coerced to ISO |
| `deadline_closed` | bool \| null | Derived (deadline vs today) |
| `detail_url` | str \| null | Scraped |
| `source` | str | `thecraftmap` or `festivalguides` |
| `event_type` | str | Classifier (one of six types) |
| `final_score` | int (0 to 100) | LLM model Stage 2 |
| `explanation` | str | LLM model Stage 2 |
| `estimated_attendance` | str | LLM model Stage 2 |
| `likely_permits` | list[str] | LLM model Stage 2 |
| `category_fit` | str (`good_fit` / `saturated`) | LLM model Stage 2 |
| `recommendation` | str (`worth_it` / `with_reservations` / `better_not`) | LLM model Stage 2 |
| `estimated_fields` | list[str] | Bookkeeping, see below |

`estimated_fields` is the honesty ledger the whole app is built around. At normalization it is filled with every optional field the source left empty, so a FestivalGuides event, which carries no venue, cost, tags, or deadline, arrives with all of those already listed. Stage 2 then appends the six AI field names. A field is in `estimated_fields` when it is not a confirmed value read off a page, whether because the source never carried it or because the model estimated it. The frontend renders a check for everything else and a diamond for everything in this list. That is the single mechanism behind the real versus estimated markers on every card. Deterministic values, like the classifier's `event_type`, are not in this list; they are treated as real, not estimated.

## 2.3 Architecture Decisions (ADRs)

### ADR-1: No database, scrape live

Each request scrapes both sources live. If a source cannot be reached it contributes nothing and its failure is named in `meta.warnings`, and the request still answers from the surviving source. If both fail, the request returns an error rather than anything stale. There is no snapshot, no cache, no persistence.

- **Why:** on-demand usage at low traffic means there is nothing worth persisting, and a degraded answer a vendor cannot see is worse than a visible failure. A cache would solve a problem this app does not have.
- **Trade-off:** every request pays full scrape latency. Acceptable at this traffic level.
- **Rejected:** a scheduled scrape into Postgres, which adds a database, a scheduler, and a staleness policy to serve a handful of requests a day.

### ADR-2: Deterministic affinity table before the LLM

A hand-tuned table of six event types against three vendor categories, each cell scored out of 40, ranks events and cuts the field to twenty before any model call.

- **Why:** the ranking logic is business judgment, not a language problem. A food festival is a bad bet for a fourth taco truck and a good one for a drinks cart, and that call should be legible in a table rather than buried in a model's reasoning. It is also free and auditable, and it produces the same answer twice.
- **Trade-off:** when several events tie at the twenty-event cut boundary, the tie is broken at random, so the exact contents of the last few slots can vary between identical requests. This is deliberate: it avoids a hidden alphabetical or scrape-order bias deciding which tied events survive.
- **Rejected:** embedding similarity, which adds a vector store and inference cost to rank about fifty rows against three categories, and produces a number nobody can explain.

### ADR-3: Two-stage LLM cascade

Stage 1 sends about twenty events to the model for a cheap numeric pre-score and gets back only an id and a score per event. Stage 2 sends the surviving five in a single batched call for rich enrichment.

- **Why:** token cost scales with what you send and what comes back. Stage 1 keeps output minimal across many events; Stage 2 spends richly on the few that will actually be shown. Enriching all twenty would cost roughly four times as much to produce the same five cards.
- **Rejected:** one enrichment call per event, which multiplies request overhead by five for no quality gain, and a single call doing both jobs, which pays rich output cost on fifteen events nobody sees.

### ADR-4: Keyword classifier over a model for event_type

Six event types assigned by keyword matching against name and description, resolved in a fixed priority order: general_fair, cultural, food, music, art_craft, sports_other.

- **Why:** the sources do not provide a category, but the vocabulary is small and stable. A deterministic classifier is instant, free, and produces the same answer twice. The fixed priority makes an event that matches several types resolve predictably rather than arbitrarily.
- **Trade-off:** an event whose name and description reveal nothing lands in sports_other as the fallback. At this scale that miss is cheap and visible.
- **Rejected:** a model-based classifier, which introduces cost and variance to solve a lookup.

### ADR-5: Degrade, do not crash, on model failure

A Stage 1 parse failure falls back to the deterministic affinity order and takes the top five. A Stage 2 parse failure fills the five cards with neutral placeholder values. A malformed model response costs result quality, never the request.

- **Why:** the output here is advisory, not a write to a system of record. A vendor is better served by a slightly weaker ranking than by an error page, and the deterministic filter has already guaranteed the five events are reasonable candidates before any model runs.
- **Rejected:** hard-failing on malformed JSON. That is the right call when bad data would poison a downstream store, but this pipeline has no store to poison and nothing after it depends on the model's output being perfect.

### ADR-6: Explicit real versus AI field markers

Every field is tracked in `estimated_fields` if it is not a confirmed scraped value. The frontend renders a check for scraped fields and a diamond for estimates, with a legend below the results.

- **Why:** the output mixes two kinds of claim. A stand cost read off the page and an attendance figure a model guessed are not the same thing, and a vendor deciding whether to commit a weekend and a few hundred dollars needs to know which is which. Presenting them identically would be the actual dishonesty.
- **Rejected:** showing only scraped fields, which strips out the analysis that makes the tool useful, and showing everything unmarked, which is a cleaner interface that lies.

### ADR-7: Permit guidance bounded to category level

California issues health permits per county across 58 counties, with rules that change. The system gives permit guidance at the category level, keeps it generic and verifiable, and carries a disclaimer that it is not legal advice and should be checked with the county.

- **Why:** county-accurate permit data would need to be maintained, and maintaining it wrong is worse than not offering it. The model is allowed to speak where its answer is general and checkable, and stops where the answer would need to be authoritative.
- **Trade-off:** the guidance is less specific than a vendor will ultimately need. That is the honest boundary, and the disclaimer states it rather than hiding it.
- **Rejected:** per-county permit detail, which promises a precision the system cannot keep current.

### ADR-8: Rate-limited public endpoint, ephemeral state only

The endpoint is capped at five searches per minute per IP, tracked by a counter in Upstash Redis that expires after sixty seconds.

- **Why:** this is a public endpoint that triggers live scrapes of third-party sites on every call, so it needs abuse control, and serverless functions are stateless between invocations, so an in-memory counter would not survive. Redis holds only an expiring counter, never event data, so the no-database rule still holds: there is no persistence, just short-lived abuse control.
- **Rejected:** no limiting, which leaves the scrapers open to abuse, and an in-process counter, which resets on every cold start and is not shared across concurrent function instances.

### ADR-9: Single Vercel project, Python plus static

`framework: null` in `vercel.json` lets Vercel run the Vite build and serve the output as static files, while deploying `/api/search.py` as a Python serverless function in the same project.

- **Why:** one deploy, one URL, one environment variable. A separate backend service would double the operational surface of a project whose backend is a single endpoint.
- **Trade-off:** serverless cold starts on the Python function, and the full scrape has to finish inside the function timeout.
- **Rejected:** a separate Python service on Railway or Render alongside a static frontend, which is the right answer only once the backend outgrows one endpoint.

## 2.4 Scope

A portfolio MVP: the smallest system that proves the pattern end to end, not a production deployment at scale.

- **Out of scope by choice:** database persistence, user accounts, saved searches, per-county permit detail, and JavaScript-rendered sources that would need a headless browser. Both current sources are server-rendered HTML, so plain requests plus BeautifulSoup are enough, and adding a browser engine to a serverless function to cover sources that do not exist yet would be cost without benefit.
- **What would come next in production:** a caching layer with a short time-to-live, so repeated searches within a window reuse a scrape instead of hitting both sources every time, which is the first thing traffic would demand and the reason the no-database decision is scoped rather than permanent. After that, additional sources beyond the two California listings, a real permit lookup to replace category-level guidance, and wiring the vendor's already-held permits through to enrichment so the guidance addresses what is still missing rather than restating what they have.

---

# 3. Build evidence

## 3.1 Stack

[GitHub - jmcc089/opportunity-finder](https://github.com/jmcc089/opportunity-finder)

| Layer | Tool | Purpose |
|---|---|---|
| **Scraping** | Python, BeautifulSoup + requests | TheCraftMap and FestivalGuides, live on each request |
| **Pipeline** | Python | Normalize, classify, affinity rank, cut to twenty |
| **AI** | DeepSeek `deepseek-v4-flash` | Two-stage scoring cascade, pre-score then enrichment |
| **API** | Flask (Vercel serverless) | `/api/search` orchestrating the full pipeline |
| **Rate limiting** | Upstash Redis | Per-IP counter, five searches per minute |
| **Frontend** | React 19, Vite, TypeScript | Search form and result cards |
| **Styling** | Tailwind CSS v3 | Sage palette, nine custom color tokens |
| **Deploy** | Vercel | Python function and static frontend, single project |

## 3.2 Request Flow

The pipeline is a funnel. Each stage narrows the field so the model only ever sees a short, pre-ranked list, and nothing reaches LLM model until Python has cut the candidates to about twenty.

```
User fills form (category, city, date range)
   │  POST /api/search
   ▼
Flask (Vercel Python serverless)
   Rate limit    → Upstash Redis, 5/min per IP → 429 if exceeded
   Scrape TCM    → live fetch → BeautifulSoup → raw dicts
   Scrape FG     → live fetch → parse lines   → raw dicts
        ↓  (one source fails → surviving source + meta.warnings; both fail → error)
   Normalize     → unified Event objects + estimated_fields[]
   City/date     → drop wrong city, drop out-of-range dates
   Classify      → event_type by keyword priority
   Affinity cut  → drop closed deadlines; rank by affinity; cut to ~20
   Stage 1       → DeepSeek pre-score ~20 → top 5 by score
   Stage 2       → DeepSeek enrich the 5 → merge AI fields, extend estimated_fields[]
   Return JSON   → { results: [...], meta: { warnings, sources_used, counts } }
   ▼
React frontend
   adaptResult   → map backend contract to card shape
   ResultCard    → score, recommendation, explanation, field rows
   FieldRow      → ✓ real or ✦ estimate per field
   Legend        → explains the two markers
```

## 3.3 Project structure

```
opportunity-finder/
├── api/
│   └── search.py            Flask entrypoint: rate limit + full pipeline
├── scrapers/
│   ├── thecraftmap.py       Live scrape → raw dicts (rich fields)
│   └── festivalguides.py    Live scrape → raw dicts (plain-text lines)
├── pipeline/
│   ├── normalize.py         Raw dicts → Event objects + estimated_fields[]
│   ├── classify.py          Keyword event_type in fixed priority order
│   ├── filter.py            Affinity rank + drop closed deadlines + cut to ~20
│   ├── stage1.py            DeepSeek pre-score ~20 → top 5
│   └── stage2.py            DeepSeek enrich the 5 → merge AI fields
├── llm/
│   └── deepseek.py          DeepSeek client (openai SDK, thinking disabled)
├── frontend/
│   └── src/
│       ├── App.tsx          Search state, API call, adaptResult mapping
│       ├── components/
│       │   ├── SearchForm.tsx    Collects category, city, dates
│       │   ├── ResultCard.tsx    Score, recommendation, field rows
│       │   ├── FieldRow.tsx      ✓ real vs ✦ estimate marker logic
│       │   └── LoadingScreen.tsx
│       └── main.tsx
├── vercel.json              framework: null, single-project config
├── requirements.txt         Python deps
└── pyproject.toml
```

## 3.4 Live Preview

https://opportunity-finder-ca.vercel.app

## 3.5 QA & Verification

The pipeline has several behaviors that are checkable rather than assumed, and each was exercised before deploy:

- **End to end against live sources.** A real search returns five ranked, enriched cards from the deployed app, which anyone can confirm at the live URL.
- **Honest failure, not a crash.** When one source is unreachable, the response carries results from the surviving source plus a warning in `meta.warnings`, and the UI shows that warning banner. When both fail, the request returns a clear error rather than an empty or stale result.
- **Graceful model degradation.** A malformed Stage 1 response falls back to the deterministic affinity order, and a malformed Stage 2 response fills neutral placeholders, so a bad model reply never breaks the request.
- **Deterministic stages are stable.** The keyword classifier and the affinity ranking produce the same output for the same input on every run, with the only intentional variation being the random tie-break at the twenty-event cut.
- **Real versus estimated markers are correct.** Fields read from a page render with a check, fields the model estimated render with a diamond, and the legend below the results explains both.
