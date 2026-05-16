# ParkSmart Chatswood — Design Spec

**Date:** 2026-05-11
**Author:** solo developer
**Status:** approved for implementation

---

## 1. Purpose

ParkSmart is a consumer product that helps residents and visitors find parking in Chatswood CBD, Sydney. It combines:

- Live car park occupancy data (TfNSW Car Park API where available, pattern-based estimation elsewhere)
- Street parking zone restrictions parsed from Willoughby Council KML
- An ML occupancy predictor trained on real TfNSW historical data
- An LLM assistant (Claude Haiku 4.5) with tool-calling that answers natural-language parking queries

All decisions are made with production quality in mind. No shortcuts that are "good enough for a demo" but wrong for real users.

---

## 2. Scope

### MVP (Plans 1–4)

1. **Live car park occupancy map** — Leaflet map of Chatswood CBD, markers colour-coded green/amber/red by occupancy %, auto-refreshed every 5 minutes. Estimation-based markers clearly distinguished from live data.
2. **Availability prediction** — given (location, datetime) within the next 7 days at hourly resolution, return predicted occupancy % and confidence score.
3. **LLM parking assistant** — chat interface, Claude with three tools: `get_live_occupancy`, `predict_availability`, `get_zone_restrictions`.
4. **Zone restrictions** — street parking rules parsed from Willoughby KML, queryable by street name.

### Future phases (not in current implementation plans)

- User accounts and saved preferences.
- Mobile-optimised or native app.
- Multi-council data (beyond Willoughby).
- Push notifications (e.g. "your usual car park is full — try Chase").
- Real-time partnerships with shopping centre operators for live CBD car park data.
- Model monitoring and automated retraining pipeline.
- Payment integration or booking.

### Out of scope (permanently)

IoT sensors, real-time traffic data, IoT hardware.

---

## 3. User success criteria

The product is working correctly when a real user can do all of the following without assistance:

1. **Recommendation.** Ask *"Where should I park near Westfield Chatswood at 6pm on Friday?"* and receive a specific named car park recommendation with occupancy %, confidence, and approximate walking distance — without being confused by the response.
2. **Restrictions.** Ask *"What are the parking rules on Victoria Avenue?"* and receive a plain-English answer accurate enough to avoid a fine.
3. **Live map.** See a map of Chatswood with at least 5 car park markers that auto-refresh, with clear visual distinction between live-data markers and estimation-based markers, so a user knows what they're looking at.

---

## 4. Locked decisions

| Area | Decision | Rationale |
|---|---|---|
| ML model | Single XGBoost occupancy regressor; penalty density as a feature if the CSV permits | Tight scope, one model one tool |
| Live data | **All 5 Chatswood CBD car parks are simulated** (TfNSW covers Park&Ride only — no Chatswood CBD entries). Real TfNSW data: Gordon (facility_id="6") and Lindfield (facility_id="34") | Honest about data coverage |
| ML training data | Real TfNSW history for Gordon and Lindfield only. Simulated car parks use the estimation model for predictions — no synthetic data in the ML training set | Cleaner data story |
| Prediction window | Up to 7 days ahead, hourly resolution | Covers "Friday 6pm" without over-engineering |
| LLM model | `claude-haiku-4-5-20251001` | Fast, cost-efficient, strong tool-calling |
| UI layout | Single page: full-bleed Leaflet map + 380px right chat drawer | Both core features visible simultaneously |
| DB | SQLite via stdlib `sqlite3`, no ORM | Appropriate for the current scale |
| State | React Context for chat, local state for the map | No state library needed at this scale |
| Backend validation | Pydantic v2 (`ConfigDict`, not `class Config`) | Matches installed library |

### Data source facts (confirmed from audit)

- TfNSW Car Park API: `https://api.transport.nsw.gov.au/v1/carpark` — `?facility=<id>` for one facility or no query param for full list. Auth: `Authorization: apikey <TOKEN>`. `spots` and `occupancy.total` are strings. `available = int(spots) - int(occupancy.total)`.
- Chatswood CBD car parks are NOT in the TfNSW feed.
- Gordon (`facility_id="6"`, 213 spots) and Lindfield (`facility_id="34"`, 94 spots) are the nearest real TfNSW facilities and serve as the live-data + ML-training anchor.
- KML file: `docs/willoughby_council_street_parking_signs_data.kml` — Point features (sign posts), CDATA contains `<B>key</B> = value` pairs. Fields: `rawSignId`, `signsPhotoURL`, `sign1_category` … `sign4_category`, `sign1_direction`, `sign1_description`, etc.
- Penalty notices: audit result determines whether the feature ships (see §13).

---

## 5. System architecture

```
┌─────────────────────────────────────────────────────────┐
│  React SPA (Vite + Tailwind)                            │
│  ┌──────────────────────┐  ┌────────────────────────┐   │
│  │ Leaflet map          │  │ Chat drawer (380px)    │   │
│  │ - 7 markers          │  │ - message list         │   │
│  │ - colour by % full   │  │ - input box            │   │
│  │ - estimated badge    │  │ - tool-call indicators │   │
│  └──────────────────────┘  └────────────────────────┘   │
└──────────────────┬─────────────────────┬────────────────┘
                   │ REST                │ SSE (chat stream)
┌──────────────────▼─────────────────────▼────────────────┐
│  FastAPI backend                                        │
│  ┌──────────┐ ┌────────────┐ ┌──────────┐ ┌──────────┐  │
│  │/occupancy│ │ /predict   │ │ /zones   │ │ /chat    │  │
│  └────┬─────┘ └─────┬──────┘ └────┬─────┘ └────┬─────┘  │
│       │             │             │            │        │
│  ┌────▼─────────────▼─────────────▼────────────▼────┐   │
│  │  Service layer (pure-python, no FastAPI imports) │   │
│  │  occupancy_service · prediction_service          │   │
│  │  zone_service · simulator · llm_service          │   │
│  └────┬─────────────┬─────────────┬────────────┬────┘   │
└───────┼─────────────┼─────────────┼────────────┼────────┘
        │             │             │            │
   ┌────▼───┐    ┌────▼────┐   ┌────▼────┐  ┌───▼────────┐
   │ TfNSW  │    │ XGBoost │   │ SQLite  │  │ Anthropic  │
   │ API +  │    │  .pkl   │   │ (zones, │  │ (Haiku 4.5)│
   │ fixtures│   │ models  │   │ history)│  │            │
   └────────┘    └─────────┘   └─────────┘  └────────────┘

Background: APScheduler polls TfNSW every 5min → occupancy_history.
            Estimation model runs every hour for 5 CBD car parks.
```

### Boundaries

- **Service layer is pure Python** — no FastAPI imports — and unit-testable without HTTP. Each service has one job.
- **`occupancy_service` hides the real/estimated split.** The `source` field in the response tells the caller which branch was used; the calling code doesn't branch on it.
- **`prediction_service` routes by source**: TfNSW car parks → XGBoost (Plan 3); CBD car parks → estimation model with future timestamp.
- **No frontend state library.** React Context for chat, local state for the map.

---

## 6. Data model

SQLite, single file `parksmart.db`. All timestamps stored as ISO8601 TEXT strings.

```sql
CREATE TABLE IF NOT EXISTS car_parks (
  id                TEXT PRIMARY KEY,
  name              TEXT NOT NULL,
  lat               REAL NOT NULL,
  lon               REAL NOT NULL,
  suburb            TEXT,
  address           TEXT,
  source            TEXT NOT NULL CHECK(source IN ('tfnsw', 'simulated')),
  tfnsw_facility_id TEXT
);

-- Available spots stored directly (not occupied) to match TfNSW's field shape.
-- ts is ISO8601 TEXT (not TIMESTAMP) — stored and queried as strings.
CREATE TABLE IF NOT EXISTS occupancy_history (
  car_park_id  TEXT NOT NULL REFERENCES car_parks(id),
  ts           TEXT NOT NULL,
  available    INTEGER NOT NULL,
  total_spots  INTEGER NOT NULL,
  PRIMARY KEY (car_park_id, ts)
);
CREATE INDEX IF NOT EXISTS idx_occ_ts ON occupancy_history(ts);

-- Each row is one KML placemark (a sign post).
-- sign_categories is a JSON array of SignEntry dicts:
-- [{"category": "No Stopping", "direction": "both", "description": "..."}]
-- street is populated by Nominatim reverse geocoding at first load (1 req/s).
CREATE TABLE IF NOT EXISTS parking_signs (
  id               INTEGER PRIMARY KEY AUTOINCREMENT,
  raw_sign_id      TEXT,
  lat              REAL NOT NULL,
  lon              REAL NOT NULL,
  street           TEXT,
  raw_description  TEXT NOT NULL,
  sign_categories  TEXT NOT NULL,
  sign_photo_url   TEXT
);
CREATE INDEX IF NOT EXISTS idx_signs_street ON parking_signs(LOWER(street));
```

### Seeded car parks

| ID | Name | Source | Spots |
|---|---|---|---|
| `sim_westfield` | Westfield Chatswood | simulated | 1400 |
| `sim_chatswood_chase` | Chatswood Chase | simulated | 850 |
| `sim_mandarin_centre` | Mandarin Centre | simulated | 280 |
| `sim_victoria_ave_cp` | Victoria Avenue Car Park | simulated | 160 |
| `sim_chatswood_west_cp` | Chatswood West Car Park | simulated | 320 |
| `tfnsw_gordon` | Park&Ride - Gordon | tfnsw | 213 |
| `tfnsw_lindfield` | Park&Ride - Lindfield | tfnsw | 94 |

Gordon and Lindfield are used for live data display and ML training. All 5 CBD car parks are pattern-estimated.

### Curated fallback

`backend/app/data/seed_zones.json` contains hand-authored structured rules for key streets (starting with Victoria Avenue). `zone_service` prefers DB-parsed KML but falls back to this file. This ensures the zone-restriction user scenario works reliably even when KML geocoding coverage is incomplete.

---

## 7. LLM tool contracts

Three tools. All return JSON-serialisable dicts. Errors are part of the return shape — no exceptions across the LLM boundary. The `source` and `model_version` fields allow the LLM to be transparent with users about data provenance.

```python
# Tool 1
get_live_occupancy(location: str) -> {
  "car_park_id": str, "name": str, "occupancy_pct": float,
  "occupied": int, "available": int, "capacity": int,
  "lat": float, "lon": float,
  "source": "tfnsw" | "simulated",  # LLM uses this to label estimates to the user
  "as_of": ISO8601
} | {"error": "no_match", "candidates": [str]}

# Tool 2
predict_availability(location: str, target_datetime: ISO8601) -> {
  "car_park_id": str, "name": str,
  "predicted_occupancy_pct": float, "confidence": float,   # 0–1
  "target_datetime": ISO8601,
  "model_version": str   # "simulator-v1" or "xgboost-v1" (Plan 3+)
} | {"error": "out_of_range" | "no_match" | "invalid_datetime", ...}
# target_datetime must be within now..now+7days; rounded to hour internally.

# Tool 3
# zone_service aggregates parking_signs rows by parsed street name into
# per-street segments before returning. Sign-level data stays internal.
get_zone_restrictions(street: str) -> {
  "street": str,
  "segments": [
    {"side": str|null, "rules_plain_english": str,
     "rules_structured": [{"days": [str], "start": "HH:MM",
                            "end": "HH:MM", "max_minutes": int|null,
                            "type": "no_stopping"|"no_parking"|"timed"|"permit_only"|"loading"|"other"}],
     "sign_photo_url": str|null}
  ]
} | {"error": "not_found"}
```

### LLM system prompt strategy

- Pinned tool-call patterns: "for 'where to park' queries, call `get_live_occupancy` first; add `predict_availability` only when the user specifies a future time; for restriction queries, call `get_zone_restrictions` directly."
- When `source == "simulated"`, the LLM is instructed to label the result as "estimated" to the user.
- Error responses include candidate lists so Claude can recover: `{"error": "no_match", "candidates": [...]}`.
- Tool-call loop capped at 5 iterations.

---

## 8. ML pipeline

### Target

`occupancy_pct = 1 - (available / total_spots)` at hour `H`, for TfNSW car parks (Gordon + Lindfield) where real historical data exists.

### Features

- `hour_of_day` (cyclical sin/cos encoding)
- `day_of_week` (cyclical encoding)
- `is_weekend` (bool)
- `is_public_holiday` (bool — static NSW holiday list)
- `car_park_id` (one-hot)
- `lag_1h`, `lag_24h`, `lag_168h` — rolling occupancy from `occupancy_history`
- `penalty_density` — if the CSV is event-level with street and timestamp: `hour_of_week → avg_penalties`. If monthly aggregate only: `lga_monthly_penalty_rate`. If unusable: feature dropped.

### Training (Plan 3)

1. Pull TfNSW historical data via `GET /v1/carpark` (full list) for Gordon and Lindfield.
2. Split: last 7 days as validation holdout.
3. Fit one XGBoost regressor across both facilities.
4. Residual model for confidence: second XGBoost trained on residuals; confidence = `1 - clip(predicted_residual / max_residual, 0, 1)`.
5. Save: `backend/models/occupancy_v1.pkl`, `residual_v1.pkl`, `feature_pipeline.pkl`.
6. Generate `models/eval_report.md` with validation MAE.

### Routing in `prediction_service`

```python
def predict_availability_tool(location, target_datetime, db_path):
    cp, candidates = find_car_park(location)
    if cp.source == "tfnsw":
        return ml_model.predict(cp.id, target_dt)        # XGBoost (Plan 3+)
    else:
        available = simulated_available(cp.id, target_dt)
        return {
            "predicted_occupancy_pct": 1 - available / cp.total_spots,
            "confidence": 0.7,
            "model_version": "simulator-v1",
        }
```

In Plan 2, the ML branch uses the estimation model as a placeholder for all car parks. Plan 3 replaces it for TfNSW parks.

### Future: retraining cadence

After Plan 3, a weekly retraining job should run `train.py` and promote the new `.pkl` only if validation MAE improves. This is a post-MVP concern — not in the current implementation plans.

---

## 9. Occupancy estimation model

Used for: live and predicted occupancy of the 5 simulated CBD car parks.

```python
def simulated_available(car_park_id: str, dt: datetime) -> int:
    cfg = BASELINES[car_park_id]  # peak_util, capacity, peak_hour, weekend_mult
    hour_factor = cosine_peak(cfg["peak_hour"], dt.hour)
    dow_mult = cfg["weekend_mult"] if dt.weekday() >= 5 else 1.0
    seed_str = f"{car_park_id}:{dt.replace(minute=0,second=0,microsecond=0).isoformat()}"
    seed_int = int(md5(seed_str).hexdigest(), 16)
    noise = Random(seed_int).uniform(-0.05, 0.05)
    occ_pct = clamp(cfg["peak_util"] * hour_factor * dow_mult + noise, 0, 1)
    return int(cfg["capacity"] * (1 - occ_pct))
```

Key properties:

- **Deterministic per `(car_park_id, hour)`** — same query always returns the same value. Uses MD5 not Python's `hash()` (which is randomised per process).
- **Same return shape as TfNSW** — returns `available` spots; `occupancy_service` merges seamlessly.
- **Calibrated patterns** — Westfield peaks at 87% utilisation midday; Victoria Ave CP peaks at 78% at 9am (weekday commuters); weekends use a per-park multiplier.

### Transparency requirement

The `source: "simulated"` field propagates from the DB row through `OccupancyResponse` to the API and the LLM tool result. The LLM system prompt instructs Claude to say "estimated" when `source == "simulated"`. The frontend renders a visual badge on estimated markers. Users should never be misled about which data is live.

---

## 10. Repository layout

```
ParkSmart/
├── PLANNING.md                    # executive summary + implementation plan table
├── CLAUDE.md                      # conventions for Claude Code
├── docs/
│   ├── willoughby_council_street_parking_signs_data.kml
│   ├── carparkswagger_prod_2.yaml # TfNSW Car Park API spec
│   └── superpowers/
│       ├── specs/
│       │   └── 2026-05-11-parksmart-design.md   # ← this file
│       └── plans/
│           ├── 2026-05-11-backend-foundation.md  # Plan 1 ✅
│           └── 2026-05-11-service-layer-api.md   # Plan 2
│
├── backend/
│   ├── pyproject.toml
│   ├── .env / .env.example
│   ├── app/
│   │   ├── main.py          # FastAPI app + lifespan
│   │   ├── config.py        # pydantic-settings
│   │   ├── db.py            # sqlite3 helpers, schema
│   │   ├── models.py        # Pydantic models
│   │   ├── scheduler.py     # APScheduler jobs
│   │   │
│   │   ├── data/
│   │   │   ├── seed_car_parks.py   # 7 car parks with lat/lon
│   │   │   ├── seed_zones.json     # curated fallback rules (Victoria Avenue etc.)
│   │   │   ├── tfnsw_client.py     # httpx wrapper, fixture fallback
│   │   │   └── kml_loader.py       # parse Willoughby KML → ParkingSignRecord
│   │   │
│   │   ├── services/
│   │   │   ├── simulator.py            # deterministic estimation model
│   │   │   ├── occupancy_service.py    # live occupancy, merge real/estimated
│   │   │   ├── prediction_service.py   # ML/simulator routing
│   │   │   ├── zone_service.py         # street lookup, seed fallback
│   │   │   └── llm_service.py          # Anthropic client, tool loop, SSE
│   │   │
│   │   └── routers/
│   │       ├── occupancy.py   # GET /api/occupancy
│   │       ├── predict.py     # GET /api/predict
│   │       ├── zones.py       # GET /api/zones?street=
│   │       └── chat.py        # POST /api/chat (SSE)
│   │
│   ├── ml/
│   │   ├── features.py    # cyclical encoding, lags, penalty join
│   │   ├── train.py       # CLI: build training set → fit → save .pkl
│   │   └── evaluate.py    # CLI: MAE on holdout → eval_report.md
│   │
│   ├── models/            # .pkl artefacts (gitignored)
│   ├── data_raw/
│   │   └── tfnsw_fixtures/   # committed fixture JSON (fallback when no API key)
│   └── tests/
│       ├── conftest.py
│       ├── test_db.py
│       ├── test_simulator.py
│       ├── test_tfnsw_client.py
│       ├── test_kml_loader.py
│       ├── test_occupancy_service.py   # Plan 2
│       ├── test_zone_service.py        # Plan 2
│       ├── test_prediction_service.py  # Plan 2
│       ├── test_llm_service.py         # Plan 2
│       └── test_api.py                 # Plan 2
│
└── frontend/                      # Plan 4
    ├── package.json               # vite, react, leaflet, tailwind, lucide-react
    ├── vite.config.ts             # proxy /api → http://localhost:8000
    └── src/
        ├── App.tsx                # layout: <Map/> + <ChatDrawer/>
        ├── api.ts                 # typed fetch wrappers
        ├── types.ts               # mirror of backend models
        ├── components/
        │   ├── Map/               # ParkingMap, CarParkMarker, ZoneSignLayer
        │   └── Chat/              # ChatDrawer, MessageList, MessageInput, ToolCallBadge
        └── hooks/
            ├── useOccupancy.ts    # polls /api/occupancy every 5min
            └── useChat.ts         # SSE chat state machine
```

---

## 11. Phased roadmap

| Plan | Description | Status |
|---|---|---|
| 1 — Backend foundation | SQLite schema, models, TfNSW client, KML loader, estimation simulator, 39 tests | ✅ Complete |
| 2 — Service layer & API | Four services (occupancy, zone, prediction, LLM), four routers, APScheduler, integration tests | Not started |
| 3 — ML pipeline | XGBoost training on TfNSW history, feature engineering, confidence model, swap prediction branch | Not started |
| 4 — Frontend | React SPA, Leaflet map, chat drawer, SSE integration, estimated-marker badge | Not started |
| Future | Auth, mobile, retraining pipeline, real CBD car park data partnerships, multi-council | Backlog |

Each plan must pass all its tests before the next plan begins.

---

## 12. Top 3 risks

### Risk 1 — Estimation model misleads users if not clearly labelled

**What goes wrong:** A user acts on "72% full" for Westfield thinking it's live sensor data. It's pattern-based. If they arrive and find it actually empty or full, trust is broken.

**Likelihood:** high (UI is the only guard). **User impact:** very high.

**Mitigation:**
1. `source: "simulated"` propagates through every layer — DB row → API response → LLM tool result → frontend badge. No layer strips it.
2. LLM system prompt instructs Claude to say "estimated based on typical patterns" when `source == "simulated"`.
3. Frontend renders a visually distinct badge on estimated markers. Plan 4 must not skip this.
4. Long-term: pursue data partnerships or scraping (with ToS review) to replace estimation with real data for CBD car parks.

### Risk 2 — Willoughby KML geocoding produces incomplete street coverage

**What goes wrong:** Nominatim reverse geocoding (1 req/s, network call) fails or times out for a meaningful fraction of placemarks. `parking_signs.street` is null for those rows. `get_zone_restrictions("Victoria Avenue")` returns empty.

**Likelihood:** medium. **User impact:** medium (zone feature specifically).

**Mitigation:**
1. `seed_zones.json` fallback guarantees at least Victoria Avenue returns correct rules regardless of geocoder coverage.
2. `zone_service` tries DB first, then seed — so DB gaps are silently covered.
3. KML loader persists raw description HTML (`raw_description` column); if structured parsing fails, the LLM can be instructed to interpret raw text as a fallback (opt-in, not on by default).
4. Geocoding is idempotent — a re-run populates more streets as Nominatim succeeds. No data is lost.

### Risk 3 — Anthropic API cost grows unbounded with real users

**What goes wrong:** Every chat message triggers at least one Claude call, possibly three (one per tool call + synthesis). At scale this is expensive. A single viral spike could rack up a significant bill.

**Likelihood:** low now, but a real concern before any public launch. **User impact:** none for the user; financial impact for the operator.

**Mitigation:**
1. Tool-call loop capped at 5 iterations per message.
2. `max_tokens=1024` per call; responses are deliberately short.
3. Before any public launch: add a request rate limit per IP (e.g. 10 messages/hour) at the FastAPI middleware layer.
4. Monitor spend via Anthropic dashboard; set billing alerts.
5. Long-term: cache common tool results (occupancy doesn't change faster than 5 min; zones are static).

---

## 13. Open questions

1. **Penalty CSV granularity** — event-level (street + timestamp) or monthly aggregate by LGA? Determines whether `penalty_density` feature ships in Plan 3 or is dropped.
2. **TfNSW historical data depth** — how many months of history are available via the API for Gordon and Lindfield? Less than 30 days may be insufficient for training; if so, the estimation model remains the prediction branch for all car parks through Plan 3 without an XGBoost upgrade.
3. **KML geocoding coverage** — what fraction of Willoughby placemarks get a parseable street name after geocoding? If <50%, the seed file needs expansion beyond Victoria Avenue before Plan 4 launches.

---

## 14. Data transparency

ParkSmart shows two kinds of data to users. This must be communicated consistently at every layer:

| Data type | Source | User-facing label |
|---|---|---|
| Live occupancy | TfNSW sensor (Gordon, Lindfield) | "Live" (green badge) |
| Estimated occupancy | Pattern model (5 CBD car parks) | "Estimated" (grey badge) |
| ML prediction (TfNSW parks) | XGBoost trained on real history | "Predicted · X% confidence" |
| Estimation-based prediction | Pattern model at future timestamp | "Estimated · typical patterns" |
| Zone restrictions | Willoughby KML + curated seed | "Source: Willoughby Council" |

The LLM must not present estimated data as live. The frontend must not skip the badge. This is a correctness requirement, not a polish concern.
