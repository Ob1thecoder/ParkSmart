# ParkSmart — Agent Handoff & Progress

ParkSmart is a **real consumer product** (not a hackathon demo) that helps residents and visitors find parking in Chatswood CBD, Sydney, Australia.

---

## Current Status

| Plan | Description | Status | Tests |
|---|---|---|---|
| 1 — Backend foundation | DB, models, seed data, simulator, TfNSW client, KML loader, FastAPI skeleton | ✅ Complete | 39 / 39 passing |
| 2 — Service layer & API | Occupancy, zone, prediction, LLM services + REST endpoints + scheduler | 🔲 Not started | — |
| 3 — ML pipeline | XGBoost training on TfNSW history data | 🔲 Not started | — |
| 4 — Frontend | React + Vite + TypeScript + Tailwind + Leaflet | 🔲 Not started | — |

**Rule:** Do not start a later plan until the earlier one passes all tests.

---

## How to verify current state

```bash
cd backend
pip install -e ".[dev]"
pytest -v --tb=short
```

Expected: **39 passed** (as of Plan 1 completion). If this number is higher, a later plan has been partially or fully implemented.

---

## Next task

Execute **Plan 2** using the written plan at:

```
docs/superpowers/plans/2026-05-11-service-layer-api.md
```

The plan has 6 tasks. Read the plan file first — every task includes full code, exact file paths, and test commands. Do not start implementation until the plan is read.

**Required before starting Plan 2:**
- `ANTHROPIC_API_KEY` must be set in `backend/.env` (needed for the LLM service task)
- All 39 Plan 1 tests must pass

---

## Repo layout

```
ParkSmart/
├── AGENTS.md                ← this file
├── CLAUDE.md                ← Claude Code conventions (gitignored)
├── PLANNING.md              ← original design notes
├── docs/
│   ├── superpowers/
│   │   ├── plans/           ← implementation plans (Plans 1–4)
│   │   └── specs/           ← design spec
├── backend/
│   ├── pyproject.toml
│   ├── .env.example         ← copy to .env and fill in keys
│   ├── app/
│   │   ├── main.py          ← FastAPI app + lifespan startup
│   │   ├── config.py        ← Settings (pydantic-settings)
│   │   ├── db.py            ← sqlite3 wrapper: init_db, get_connection
│   │   ├── models.py        ← shared Pydantic v2 models
│   │   ├── scheduler.py     ← APScheduler (Plan 2)
│   │   ├── data/
│   │   │   ├── seed_car_parks.py   ← 7 car parks (5 sim + Gordon + Lindfield)
│   │   │   ├── seed_zones.json     ← Victoria Avenue curated restrictions
│   │   │   ├── tfnsw_client.py     ← TfNSW API client + fixture fallback
│   │   │   └── kml_loader.py       ← Willoughby KML parser
│   │   ├── services/               ← pure Python, no FastAPI imports
│   │   │   ├── simulator.py        ← deterministic occupancy simulator
│   │   │   ├── occupancy_service.py  (Plan 2)
│   │   │   ├── zone_service.py       (Plan 2)
│   │   │   ├── prediction_service.py (Plan 2)
│   │   │   └── llm_service.py        (Plan 2)
│   │   └── routers/                  (Plan 2)
│   ├── data_raw/
│   │   └── tfnsw_fixtures/  ← committed JSON fixtures (fallback when no API key)
│   └── tests/
└── frontend/                ← React + Vite (Plan 4)
```

---

## Key conventions (summary — see CLAUDE.md for full detail)

- **Python 3.11+**, FastAPI, Pydantic v2 (`ConfigDict`, not `class Config`)
- **No ORM** — stdlib `sqlite3` only; always use `get_connection(db_path)` context manager
- **Services** in `app/services/` must have zero FastAPI imports — pure Python, testable without HTTP
- **Tests**: always pass `geocode=False` to `parse_kml`; mock `anthropic.AsyncAnthropic` in LLM tests; use `seeded_db` fixture for tests that need car parks in the DB
- **No commits in plan steps** — the developer commits manually
- **No comments** unless the WHY is non-obvious

---

## Critical data-source facts

| Fact | Impact |
|---|---|
| Chatswood CBD has **no entries** in the TfNSW Car Park API | All 5 Chatswood car parks are `source="simulated"` |
| TfNSW fields: `spots` (string, total), `occupancy.total` (string, occupied) | `available = int(spots) - int(occupancy.total)` — derived, not from API |
| Gordon (`facility_id="6"`, 213 spots) and Lindfield (`facility_id="34"`, 94 spots) are the real TfNSW facilities | Used for live data and ML training |
| Willoughby KML has **no street names** | Nominatim reverse geocoding at load time, 1 req/s, `time.sleep(1.0)` between calls |
| KML CDATA format: `<B>key</B> = value` pairs | Parsed by `_parse_fields()` in kml_loader.py |
| Penalty notice data (state-wide NSW aggregate) has no location field | **Not used** — do not add penalty-based ML features |

---

## Environment variables

| Variable | Required for | Default |
|---|---|---|
| `ANTHROPIC_API_KEY` | `/api/chat` LLM endpoint (Plan 2) | — |
| `TFNSW_API_KEY` | Live TfNSW polling (falls back to fixtures if absent) | — |
| `DB_PATH` | SQLite file path | `parksmart.db` |
| `FIXTURES_DIR` | JSON fixture directory | `data_raw/tfnsw_fixtures` |

Copy `backend/.env.example` to `backend/.env` and fill in keys before running.

---

## Car park IDs

| ID | Name | Source | Spots |
|---|---|---|---|
| `sim_westfield` | Westfield Chatswood | simulated | 1400 |
| `sim_chatswood_chase` | Chatswood Chase | simulated | 850 |
| `sim_mandarin_centre` | Mandarin Centre | simulated | 280 |
| `sim_victoria_ave_cp` | Victoria Avenue Car Park | simulated | 160 |
| `sim_chatswood_west_cp` | Chatswood West Car Park | simulated | 320 |
| `tfnsw_gordon` | Park&Ride - Gordon | tfnsw | 213 |
| `tfnsw_lindfield` | Park&Ride - Lindfield | tfnsw | 94 |
