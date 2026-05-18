# ParkSmart Chatswood — Design Spec

**Date:** 2026-05-11 · **Revision:** 2026-05-18 — facility list, multi-site regression, **inference lag widening + predict troubleshooting + `/api/predict` id preference**
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
3. **Live map.** See a map centred on Chatswood with car park markers (simulated CBD + TfNSW Park&Rides) that auto-refresh, with clear visual distinction between live TfNSW data and pattern-based estimates.

---

## 4. Locked decisions

| Area | Decision | Rationale |
|---|---|---|
| ML model | **Two chained XGBoost regressors**: (1) occupancy fraction 0–1, (2) absolute residual for confidence — see §8 | Implemented in `backend/app/ml/train.py`; penalty density omitted |
| Live data | **Chatswood CBD garages are simulated** (TfNSW has no CBD entries). **44 TfNSW Park&Ride facilities** are seeded (`app/data/tfnsw_facility_seed.py`); Gordon & Lindfield keep stable app IDs (`tfnsw_gordon`, `tfnsw_lindfield`) | Honest coverage; commuter sites are live where the API responds |
| ML training data | **All seeded TfNSW car parks**: rows in `occupancy_history` keyed by TfNSW `car_park_id` contribute; **facility identity** encoded as binary columns (`park__<id>` per site). Simulated garages never appear in training | One model learns shared calendar effects; sparse sites rely on pooled signal until history grows |
| Prediction window | Up to 7 days ahead, hourly resolution | Covers "Friday 6pm" without over-engineering |
| LLM model | `claude-haiku-4-5-20251001` | Fast, cost-efficient, strong tool-calling |
| UI layout | Single page: full-bleed Leaflet map + 380px right chat drawer | Both core features visible simultaneously |
| DB | SQLite (dev) / optional PostgreSQL (`DATABASE_URL`) via `db.py` wrapper | Persisted `/data/parksmart.db` on Fly with volume mount |
| State | React Context for chat, local state for the map | No state library needed at this scale |
| Backend validation | Pydantic v2 (`ConfigDict`, not `class Config`) | Matches installed library |

### Data source facts (confirmed from audit)

- TfNSW Car Park API: `https://api.transport.nsw.gov.au/v1/carpark` — `?facility=<id>` for one facility or no query param for full list. Auth: `Authorization: apikey <TOKEN>`. `spots` and `occupancy.total` are strings. `available = int(spots) - int(occupancy.total)`.
- Chatswood CBD car parks are NOT in the TfNSW feed.
- Gordon (`facility_id="6"`) and Lindfield (`facility_id="34"`) are the closest North Shore Park&Rides to Chatswood and keep legacy stable IDs; **40+ additional TfNSW facilities** ship for map + polling (+ training once history exists).
- KML file: `docs/willoughby_council_street_parking_signs_data.kml` — Point features (sign posts), CDATA contains `<B>key</B> = value` pairs. Fields: `rawSignId`, `signsPhotoURL`, `sign1_category` … `sign4_category`, `sign1_direction`, `sign1_description`, etc.
- Penalty notices: audit result determines whether the feature ships (see §13).

---

## 5. System architecture

```
┌─────────────────────────────────────────────────────────┐
│  React SPA (Vite + Tailwind)                            │
│  ┌──────────────────────┐  ┌────────────────────────┐   │
│  │ Leaflet map          │  │ Chat drawer (380px)    │   │
│  │ - N markers (API)    │  │ - message list         │   │
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

Background: APScheduler polls TfNSW full-list every 5min → occupancy_history.
            Estimation model runs hourly for simulated CBD garages.
```

### Boundaries

- **Service layer is pure Python** — no FastAPI imports — and unit-testable without HTTP. Each service has one job.
- **`occupancy_service` hides the real/estimated split.** The `source` field in the response tells the caller which branch was used; the calling code doesn't branch on it.
- **`prediction_service` routes by source**: TfNSW → `predictor.predict` **when `models/occupancy_v1.pkl` exists** and feature layout matches (`feature_columns` in bundle); otherwise **every TfNSW site falls back to exactly 50% full** (`capacity//2`, `simulator-v1`). CBD garages → deterministic simulator at future hour.
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

Car parks live in **`backend/app/data/seed_car_parks.py`** (+ TfNSW metadata in **`tfnsw_facility_seed.py`**):

| Bucket | Role |
|--------|------|
| **8× `sim_*`** | Chatswood / North Shore garages — deterministic pattern model; `source="simulated"`. |
| **44× TfNSW** | Park&Rides from TfNSW documentation — live polling + history; **`tfnsw_gordon`** / **`tfnsw_lindfield`** are stable aliases for API facilities **6** and **34**. Other IDs follow `tfnsw_facility_<facility_id>`. |

Gordon remains the prototypical commuter anchor (~3 km north of CBD). All CBD-facing garages remain estimated.

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

### Target (regression)

Hourly occupancy **fraction**: `occupancy_frac = clip(1 − available/total_spots, 0, 1)` after aggregating readings to **`floor`** hour (`build_training_frame`).

### Features

- **`hour_*` / `dow_*`**: cyclic sin/cos for hour-of-day (24) and weekday (7).
- **`is_weekend`**, **`is_public_holiday`** (NSW, `holidays` package).
- **Facility encoding**: binary column **`park__<car_park_id>`** per seeded TfNSW site (same order as `TFNSW_CAR_PARKS`; Gordon/Lindfield use `park__tfnsw_gordon` / `park__tfnsw_lindfield`).
- **`lag_24h`**, **`lag_168h`**: occupancy fraction at the same `(site, clock-hour)` shifted back 24h / 168h; missing buckets fall back to that site’s mean occupancy in-frame.
- **Dropped / future**: `penalty_density` (no production feature yet).

### Data collection → training

1. **Backfill history**: `python -m app.ml.collect_history --days 120` (requires `TFNSW_API_KEY`) writes `occupancy_history` rows for **every seeded TfNSW** `car_park_id`.
2. **Train**: `python -m app.ml.train` reads those rows via `features.build_training_frame`, holds out the **last N days** (default **7**) for validation, fits **`XGBRegressor`** for mean occupancy and a second **`XGBRegressor`** on training-set absolute residuals (confidence heuristic).
3. **Publish**: artefacts go to **`backend/models/occupancy_v1.pkl`** + **`backend/models/eval_report.md`** (gitignored bundles are copied into Docker images explicitly if needed).
4. **Minimum samples**: training refuses to run unless enough hourly rows exist (`max(300, min(5000, 8 × (#TfNSW sites)))` guard).

### Inference

`predictor.predict` builds the same **`feature_columns`** bundle the trainer saved. It fills **`lag_24h` / `lag_168h`** by querying **`occupancy_history` for that `car_park_id`**: prefer reading within **±90 min** of nominal lag time; if absent, **±72 h** around nominal; else latest row on/before nominal (up to **180 days** back); else **`train_mean_occupancy`**. *Narrow ±90 min–only + global mean fallback used to make sparse TfNSW sites share identical lags and flatten forecasts; the wider tiers (2026-05) restore site-specific signal.*

**`GET /api/predict`:** `location` may be **`car_park_id`** (preferred when batching from occupancy) or natural language; **`find_car_park`** uses exact id/name match then fuzzy match with **cutoff 0.55** to avoid spurious matches.

### Inference troubleshooting (observability)

| Symptom | Likely cause |
|--------|----------------|
| All TfNSW predictions **~50%**, `simulator-v1` | **No `occupancy_v1.pkl`** on the API host (stub path). |
| Many TfNSW predictions **identical %** with `xgboost-v1` | **Sparse lags** collapsing to same mean (mitigated by ±72 h + per-site last-known row); re-check `occupancy_history` coverage or retrain after data grows. |

```python
def predict_availability_tool(location, target_datetime, db_path):
    target_dt = parse_iso8601(target_datetime)
    cp, candidates = find_car_park(location)
    if cp.source == "tfnsw":
        result = predictor.predict(cp.id, target_dt, db_path)
        if result is not None:
            return result
        return estimator_fallback_for_tfnsw(cp.id, cp.name, target_dt)  # e.g. 50% occupancy
    return simulator_prediction(cp.id, cp.name, target_dt)
```

### Retraining

Post-MVP: scheduled `collect_history` + `train` when validation MAE improves; not automated in-repo today.

---

## 9. Occupancy estimation model

Used for: live and predicted occupancy of **all** seeded `sim_*` garages (see `seed_car_parks`).

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
│   │   │   ├── seed_car_parks.py   # simulated + TfNSW facilities (~52 total rows)
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
2. **TfNSW historical coverage** — new facilities need weeks of `/history` ingestion before contributing meaningful rows; the training gate enforces minimum hourly samples across the pooled frame.
3. **KML geocoding coverage** — what fraction of Willoughby placemarks get a parseable street name after geocoding? If <50%, the seed file needs expansion beyond Victoria Avenue before Plan 4 launches.

---

## 14. Data transparency

ParkSmart shows two kinds of data to users. This must be communicated consistently at every layer:

| Data type | Source | User-facing label |
|---|---|---|
| Live occupancy | TfNSW sensors (Park&Ride sites seeded in DB) | "Live" (green badge when `source=tfnsw`) |
| Estimated occupancy | Pattern model (`sim_*` CBD / retail garages) | "Estimated" (grey badge) |
| ML prediction (TfNSW parks) | XGBoost trained on real history | "Predicted · X% confidence" |
| Estimation-based prediction | Pattern model at future timestamp | "Estimated · typical patterns" |
| Zone restrictions | Willoughby KML + curated seed | "Source: Willoughby Council" |

The LLM must not present estimated data as live. The frontend must not skip the badge. This is a correctness requirement, not a polish concern.
