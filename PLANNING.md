# ParkSmart Chatswood — PLANNING

> Full design spec: [`docs/superpowers/specs/2026-05-11-parksmart-design.md`](docs/superpowers/specs/2026-05-11-parksmart-design.md)

## What we're building

A consumer product that helps residents and visitors find parking in Chatswood CBD, Sydney.

- Live car park occupancy (TfNSW Car Park API for Gordon + Lindfield; pattern-based estimation for 5 Chatswood CBD car parks the API doesn't cover)
- Street parking zone restrictions parsed from Willoughby Council KML
- An ML occupancy predictor trained on real TfNSW historical data (XGBoost, Plan 3)
- An LLM assistant (Claude Haiku 4.5) with three tool-calls

All decisions are made with production quality in mind.

## Implementation plans

| Plan | Description | Status |
|---|---|---|
| 1 — Backend foundation | SQLite schema, models, TfNSW client, KML loader, estimation simulator, 39 tests | ✅ Complete |
| 2 — Service layer & API | Four services, four routers, APScheduler, integration tests | Not started |
| 3 — ML pipeline | XGBoost on TfNSW history, confidence model, swap prediction branch | Not started |
| 4 — Frontend | React SPA, Leaflet map, chat drawer, SSE integration | Not started |

Do not start a later plan until the earlier one passes all tests.

Plan files: `docs/superpowers/plans/`

## Locked decisions

| Area | Decision |
|---|---|
| Live data | All 5 Chatswood CBD car parks are `source=simulated` (not in TfNSW feed). Real TfNSW: Gordon (`facility_id="6"`) + Lindfield (`facility_id="34"`). |
| ML training | All **seeded TfNSW** `car_park_id`s with history contribute; **`park__…` one-hot** features (**see `features.py`**). Operational notes: **`docs/ML_TRAINING_GUIDE.md`** §Module 10 (flat predictions, **`simulator-v1`** = missing `.pkl`, lag lookup). **`docs/DEPLOYMENT.md`** §TfNSW occupancy model. |
| Prediction | 7-day horizon, hourly resolution. Simulated garages → pattern model; TfNSW → **XGBoost when `occupancy_v1.pkl` present**, else fallback **exact 50%** per site (`simulator-v1`). Frontend batch → **`car_park_id`** as **`/api/predict?location=`**. |
| LLM | `gpt-4o-mini` (OpenAI) |
| UI | Single page: full-bleed Leaflet map + 380px right chat drawer |
| Transparency | `source: "simulated"` propagates through every layer. LLM labels estimates as "estimated". Frontend shows a visual badge. |

## User success criteria

1. A user asks "Where should I park near Westfield at 6pm Friday?" and gets a specific named recommendation with occupancy %, confidence, and walking distance — without confusion.
2. A user asks "What are the parking rules on Victoria Avenue?" and gets an answer accurate enough to avoid a fine.
3. The map shows at least 7 car park markers (5 estimated + 2 live) that auto-refresh, with clear visual distinction between live and estimated.

## Car park reference

| ID | Name | Source | Spots |
|---|---|---|---|
| `sim_westfield` | Westfield Chatswood | simulated | 1400 |
| `sim_chatswood_chase` | Chatswood Chase | simulated | 850 |
| `sim_mandarin_centre` | Mandarin Centre | simulated | 280 |
| `sim_victoria_ave_cp` | Victoria Avenue Car Park | simulated | 160 |
| `sim_chatswood_west_cp` | Chatswood West Car Park | simulated | 320 |
| `tfnsw_gordon` | Park&Ride - Gordon | tfnsw | 213 |
| `tfnsw_lindfield` | Park&Ride - Lindfield | tfnsw | 94 |

## Tech stack (fixed)

- **Backend:** Python 3.11+, FastAPI, SQLite (stdlib sqlite3), httpx, APScheduler 3.x
- **ML:** pandas, scikit-learn, XGBoost
- **LLM:** `openai.AsyncOpenAI`, gpt-4o-mini, tool-calling pattern
- **Frontend:** React (Vite), Leaflet.js, Tailwind CSS, TypeScript
- **KML:** lxml

## Top 3 risks

1. **Estimation model misleads users** — `source: "simulated"` must propagate through every layer; frontend badge is mandatory, not polish.
2. **KML geocoding coverage gaps** — `seed_zones.json` fallback guarantees Victoria Avenue; expand seed before Plan 4 if coverage is low.
3. **Anthropic API cost at scale** — 5-iteration tool loop cap, `max_tokens=1024`, rate-limit middleware before any public launch.

## Open questions (resolve before Plan 3)

- Penalty CSV granularity: event-level or monthly aggregate? Determines whether `penalty_density` feature ships.
- TfNSW historical data depth: enough rows for Gordon + Lindfield to train XGBoost reliably?
- KML geocoding coverage: fraction of placemarks with parseable street name after Nominatim run?
