# Service Layer & API Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the four services (occupancy, zone, prediction, LLM) and their corresponding FastAPI routers, plus the APScheduler background jobs, so all three demo scenarios work end-to-end.

**Architecture:** Each service is a pure-Python module (no FastAPI imports) with one clearly defined job. Routers are thin wrappers that call one service function and return the result. The LLM service uses an async Anthropic client so SSE streaming works natively in FastAPI without thread pools.

**Tech Stack:** FastAPI, APScheduler 3.x, anthropic SDK (AsyncAnthropic), difflib (stdlib), Python 3.11+

**Depends on:** Plan 1 (backend-foundation) — must be complete first. Assumes `app.db`, `app.models`, `app.config`, `app.data.seed_car_parks`, `app.data.tfnsw_client`, `app.services.simulator` all exist as defined in Plan 1.

---

## Scope note

This is Plan 2 of 4. It produces a fully functional backend API. It does **not** yet include:
- XGBoost ML model (Plan 3) — `prediction_service` uses the simulator as placeholder for all car parks
- Frontend (Plan 4)

---

## File structure

```
backend/
├── app/
│   ├── models.py                         MODIFY — add OccupancyResponse, ZoneSegment, ZoneResponse
│   ├── config.py                         MODIFY — add get_settings() for FastAPI Depends
│   ├── main.py                           MODIFY — CORS, routers, scheduler, backfill
│   ├── scheduler.py                      CREATE
│   ├── services/
│   │   ├── occupancy_service.py          CREATE
│   │   ├── zone_service.py               CREATE
│   │   ├── prediction_service.py         CREATE
│   │   └── llm_service.py               CREATE
│   └── routers/
│       ├── __init__.py                   CREATE — empty
│       ├── occupancy.py                  CREATE — GET /api/occupancy
│       ├── zones.py                      CREATE — GET /api/zones?street=
│       ├── predict.py                    CREATE — GET /api/predict
│       └── chat.py                       CREATE — POST /api/chat (SSE)
└── tests/
    ├── conftest.py                       MODIFY — add seeded_db fixture
    ├── test_occupancy_service.py         CREATE
    ├── test_zone_service.py              CREATE
    ├── test_prediction_service.py        CREATE
    ├── test_llm_service.py               CREATE
    └── test_api.py                       CREATE — TestClient integration tests
```

---

## Task 1: Extend models, config, and conftest

**Files:**
- Modify: `backend/app/models.py`
- Modify: `backend/app/config.py`
- Modify: `backend/tests/conftest.py`

- [ ] **Step 1.1: Add response models to `backend/app/models.py`**

Append to the end of the existing file (after `PredictionResult`):

```python
class OccupancyResponse(BaseModel):
    """API + LLM tool response for a single car park's current occupancy."""
    car_park_id: str
    name: str
    occupancy_pct: float          # 0.0–1.0
    occupied: int
    available: int
    capacity: int
    lat: float
    lon: float
    source: Literal["tfnsw", "simulated"]
    as_of: str                    # ISO8601 string as stored in DB


class ZoneSegment(BaseModel):
    """One group of signs on the same side of a street."""
    side: str | None = None       # "left" | "right" | null (both/unknown)
    rules_plain_english: str
    rules_structured: list[RestrictionRule] = []
    sign_photo_url: str | None = None


class ZoneResponse(BaseModel):
    street: str
    segments: list[ZoneSegment]


class ChatRequest(BaseModel):
    message: str
    history: list[dict] = []     # [{role: "user"|"assistant", content: str}]
```

- [ ] **Step 1.2: Add `get_settings()` to `backend/app/config.py`**

Append to the end of the existing file:

```python
def get_settings() -> Settings:
    return settings
```

- [ ] **Step 1.3: Add `seeded_db` fixture to `backend/tests/conftest.py`**

Append to the existing conftest.py (keep existing fixtures):

```python
from app.data.seed_car_parks import seed as _seed_car_parks


@pytest.fixture
def seeded_db(db_path: Path) -> Path:
    """DB with schema initialised AND all car parks seeded."""
    _seed_car_parks(db_path)
    return db_path
```

- [ ] **Step 1.4: Verify pytest collects without error**

```bash
cd backend
pytest --collect-only
```

Expected: collection succeeds (existing tests listed, no errors).

---

## Task 2: `occupancy_service.py` + `GET /api/occupancy`

**Files:**
- Create: `backend/app/services/occupancy_service.py`
- Create: `backend/app/routers/__init__.py`
- Create: `backend/app/routers/occupancy.py`
- Create: `backend/tests/test_occupancy_service.py`

- [ ] **Step 2.1: Write the failing tests**

Create `backend/tests/test_occupancy_service.py`:

```python
import pytest
from datetime import datetime
from pathlib import Path
from app.config import Settings
from app.services import occupancy_service
from app.models import OccupancyResponse, CarPark
from app.db import get_connection


def _make_settings(seeded_db: Path) -> Settings:
    return Settings(db_path=seeded_db, tfnsw_api_key="", anthropic_api_key="")


# --- get_all_occupancy ---

def test_get_all_occupancy_returns_seven_car_parks(seeded_db):
    settings = _make_settings(seeded_db)
    result = occupancy_service.get_all_occupancy(seeded_db, settings)
    assert len(result) == 7  # 5 sim + 2 tfnsw


def test_get_all_occupancy_response_shape(seeded_db):
    settings = _make_settings(seeded_db)
    for item in occupancy_service.get_all_occupancy(seeded_db, settings):
        assert isinstance(item, OccupancyResponse)
        assert 0.0 <= item.occupancy_pct <= 1.0
        assert item.available >= 0
        assert item.capacity > 0
        assert item.occupied + item.available == item.capacity


def test_get_all_occupancy_prefers_history_row(seeded_db):
    settings = _make_settings(seeded_db)
    # Insert a known row into occupancy_history
    with get_connection(seeded_db) as con:
        con.execute(
            "INSERT INTO occupancy_history (car_park_id, ts, available, total_spots) "
            "VALUES ('sim_westfield', '2026-05-11T10:00:00', 42, 1400)"
        )
    result = occupancy_service.get_all_occupancy(seeded_db, settings)
    westfield = next(r for r in result if r.car_park_id == "sim_westfield")
    assert westfield.available == 42
    assert westfield.as_of == "2026-05-11T10:00:00"


# --- find_car_park ---

def test_find_car_park_exact_name():
    cp, candidates = occupancy_service.find_car_park("Westfield Chatswood")
    assert cp is not None
    assert cp.id == "sim_westfield"


def test_find_car_park_fuzzy_partial():
    cp, candidates = occupancy_service.find_car_park("westfield")
    assert cp is not None
    assert cp.id == "sim_westfield"


def test_find_car_park_by_id():
    cp, candidates = occupancy_service.find_car_park("sim_mandarin_centre")
    assert cp is not None
    assert cp.id == "sim_mandarin_centre"


def test_find_car_park_no_match_returns_candidates():
    cp, candidates = occupancy_service.find_car_park("Completely Unknown Venue")
    assert cp is None
    assert len(candidates) > 0


# --- get_live_occupancy_tool ---

def test_get_live_occupancy_tool_success(seeded_db):
    settings = _make_settings(seeded_db)
    result = occupancy_service.get_live_occupancy_tool("Westfield", seeded_db, settings)
    assert "error" not in result
    assert result["car_park_id"] == "sim_westfield"
    assert "occupancy_pct" in result
    assert "lat" in result


def test_get_live_occupancy_tool_no_match(seeded_db):
    settings = _make_settings(seeded_db)
    result = occupancy_service.get_live_occupancy_tool("NotARealPlace", seeded_db, settings)
    assert result["error"] == "no_match"
    assert "candidates" in result


# --- refresh_sim ---

def test_refresh_sim_writes_occupancy_history(seeded_db):
    settings = _make_settings(seeded_db)
    dt = datetime(2026, 5, 11, 14, 0, 0)
    occupancy_service.refresh_sim(seeded_db, dt=dt)
    with get_connection(seeded_db) as con:
        rows = con.execute(
            "SELECT count(*) as n FROM occupancy_history WHERE ts LIKE '2026-05-11T14%'"
        ).fetchone()
    assert rows["n"] == 5  # one row per sim car park


def test_refresh_sim_is_idempotent(seeded_db):
    settings = _make_settings(seeded_db)
    dt = datetime(2026, 5, 11, 15, 0, 0)
    occupancy_service.refresh_sim(seeded_db, dt=dt)
    occupancy_service.refresh_sim(seeded_db, dt=dt)  # second call must not raise
    with get_connection(seeded_db) as con:
        count = con.execute(
            "SELECT count(*) as n FROM occupancy_history WHERE car_park_id='sim_westfield'"
        ).fetchone()["n"]
    assert count == 1  # INSERT OR IGNORE: still just one row


# --- backfill_sim_history ---

def test_backfill_inserts_rows_for_all_sim_parks(seeded_db):
    occupancy_service.backfill_sim_history(seeded_db, days=2)
    with get_connection(seeded_db) as con:
        count = con.execute(
            "SELECT count(*) as n FROM occupancy_history"
        ).fetchone()["n"]
    # 5 sim parks × 2 days × 24 hours = 240 rows
    assert count == 240
```

- [ ] **Step 2.2: Run tests — confirm they fail**

```bash
cd backend
pytest tests/test_occupancy_service.py -v
```

Expected: `ImportError: cannot import name 'occupancy_service' from 'app.services'`

- [ ] **Step 2.3: Create `backend/app/services/occupancy_service.py`**

```python
import difflib
import logging
from datetime import datetime, timedelta, timezone
from pathlib import Path

from app.config import Settings
from app.data.seed_car_parks import ALL_CAR_PARKS, SIM_CAR_PARK_IDS, get_capacity, TFNSW_CAR_PARKS
from app.db import get_connection
from app.models import CarPark, OccupancyResponse
from app.services.simulator import simulated_available

log = logging.getLogger(__name__)

_NAME_INDEX: dict[str, CarPark] = {}
for _cp in ALL_CAR_PARKS:
    _NAME_INDEX[_cp.id.lower()] = _cp
    _NAME_INDEX[_cp.name.lower()] = _cp


def find_car_park(location: str) -> tuple[CarPark | None, list[str]]:
    """Fuzzy-match `location` to a car park. Returns (match, all_names)."""
    normalized = location.lower().strip()
    all_names = [cp.name for cp in ALL_CAR_PARKS]

    if normalized in _NAME_INDEX:
        return _NAME_INDEX[normalized], all_names

    matches = difflib.get_close_matches(normalized, _NAME_INDEX.keys(), n=1, cutoff=0.4)
    if matches:
        return _NAME_INDEX[matches[0]], all_names

    return None, all_names


def get_all_occupancy(db_path: Path, settings: Settings) -> list[OccupancyResponse]:
    """Return current occupancy for every car park. Reads history if available,
    falls back to on-demand computation for car parks with no history rows."""
    result = []
    with get_connection(db_path) as con:
        for cp in ALL_CAR_PARKS:
            row = con.execute(
                "SELECT ts, available, total_spots FROM occupancy_history "
                "WHERE car_park_id = ? ORDER BY ts DESC LIMIT 1",
                (cp.id,),
            ).fetchone()

            if row:
                available = row["available"]
                total = row["total_spots"]
                as_of = row["ts"]
            else:
                total = get_capacity(cp.id)
                if cp.source == "simulated":
                    available = simulated_available(cp.id, datetime.now())
                else:
                    available = total  # safe default: fully empty before first poll
                as_of = datetime.now().isoformat()

            occupied = total - available
            occ_pct = round(occupied / total, 4) if total > 0 else 0.0
            result.append(
                OccupancyResponse(
                    car_park_id=cp.id,
                    name=cp.name,
                    occupancy_pct=occ_pct,
                    occupied=occupied,
                    available=available,
                    capacity=total,
                    lat=cp.lat,
                    lon=cp.lon,
                    source=cp.source,
                    as_of=as_of,
                )
            )
    return result


def get_live_occupancy_tool(
    location: str, db_path: Path, settings: Settings
) -> dict:
    """LLM tool 1: get_live_occupancy. Returns the tool contract dict."""
    cp, candidates = find_car_park(location)
    if cp is None:
        return {"error": "no_match", "candidates": candidates}

    all_occ = get_all_occupancy(db_path, settings)
    occ = next((o for o in all_occ if o.car_park_id == cp.id), None)
    if occ is None:
        return {"error": "no_match", "candidates": candidates}

    return {
        "car_park_id": occ.car_park_id,
        "name": occ.name,
        "occupancy_pct": occ.occupancy_pct,
        "occupied": occ.occupied,
        "available": occ.available,
        "capacity": occ.capacity,
        "lat": occ.lat,
        "lon": occ.lon,
        "source": occ.source,
        "as_of": occ.as_of,
    }


def refresh_tfnsw(db_path: Path, settings: Settings) -> None:
    """Poll TfNSW full-list and upsert into occupancy_history. Called by scheduler."""
    from app.data.tfnsw_client import TfNSWClient

    client = TfNSWClient(settings)
    try:
        snapshots = client.get_full_list(fixture_name="full_list")
    except Exception as exc:
        log.warning("TfNSW full-list failed: %s", exc)
        return
    finally:
        client.close()

    snap_by_fid = {s.facility_id: s for s in snapshots}
    with get_connection(db_path) as con:
        for cp in TFNSW_CAR_PARKS:
            snap = snap_by_fid.get(cp.tfnsw_facility_id)
            if snap is None:
                log.debug("No TfNSW data for facility %s (%s)", cp.tfnsw_facility_id, cp.id)
                continue
            con.execute(
                "INSERT OR REPLACE INTO occupancy_history "
                "(car_park_id, ts, available, total_spots) VALUES (?, ?, ?, ?)",
                (cp.id, snap.ts.isoformat(), snap.available, snap.total_spots),
            )
    log.info("TfNSW occupancy refreshed for %d facilities", len(snap_by_fid))


def refresh_sim(db_path: Path, dt: datetime | None = None) -> None:
    """Write one simulated snapshot per sim car park for the given hour. Called by scheduler."""
    if dt is None:
        dt = datetime.now(timezone.utc)
    dt = dt.replace(minute=0, second=0, microsecond=0)

    with get_connection(db_path) as con:
        for car_park_id in SIM_CAR_PARK_IDS:
            available = simulated_available(car_park_id, dt)
            capacity = get_capacity(car_park_id)
            con.execute(
                "INSERT OR IGNORE INTO occupancy_history "
                "(car_park_id, ts, available, total_spots) VALUES (?, ?, ?, ?)",
                (car_park_id, dt.isoformat(), available, capacity),
            )
    log.debug("Sim occupancy refreshed for %s", dt.isoformat())


def backfill_sim_history(db_path: Path, days: int = 90) -> None:
    """Seed the last `days` × 24 hourly rows for all sim car parks (idempotent)."""
    now = datetime.now(timezone.utc).replace(minute=0, second=0, microsecond=0)
    rows = []
    for car_park_id in SIM_CAR_PARK_IDS:
        capacity = get_capacity(car_park_id)
        for h in range(days * 24):
            dt = now - timedelta(hours=h)
            available = simulated_available(car_park_id, dt)
            rows.append((car_park_id, dt.isoformat(), available, capacity))

    with get_connection(db_path) as con:
        con.executemany(
            "INSERT OR IGNORE INTO occupancy_history "
            "(car_park_id, ts, available, total_spots) VALUES (?, ?, ?, ?)",
            rows,
        )
    log.info("Backfilled %d sim history rows (%d days)", len(rows), days)
```

- [ ] **Step 2.4: Create `backend/app/routers/__init__.py`** (empty file)

- [ ] **Step 2.5: Create `backend/app/routers/occupancy.py`**

```python
from fastapi import APIRouter, Depends
from app.config import Settings, get_settings
from app.models import OccupancyResponse
from app.services import occupancy_service

router = APIRouter()


@router.get("/occupancy", response_model=list[OccupancyResponse])
def list_occupancy(settings: Settings = Depends(get_settings)) -> list[OccupancyResponse]:
    return occupancy_service.get_all_occupancy(settings.db_path, settings)
```

- [ ] **Step 2.6: Run tests — confirm they pass**

```bash
cd backend
pytest tests/test_occupancy_service.py -v
```

Expected: all 12 tests PASS.

---

## Task 3: `zone_service.py` + `GET /api/zones`

**Files:**
- Create: `backend/app/services/zone_service.py`
- Create: `backend/app/routers/zones.py`
- Create: `backend/tests/test_zone_service.py`

**Context:** The zone service looks up parking signs for a street from two sources in order:
1. `parking_signs` table in the DB (signs loaded from the Willoughby KML in Plan 1's lifespan startup). Grouped by sign direction → segment side.
2. `seed_zones.json` fallback — hand-written Victoria Avenue rules that guarantee the demo scenario works even if the KML geocoding failed.

- [ ] **Step 3.1: Write the failing tests**

Create `backend/tests/test_zone_service.py`:

```python
import json
import pytest
from pathlib import Path
from app.config import Settings
from app.db import get_connection
from app.services import zone_service


# --- get_zone_restrictions ---

def test_victoria_avenue_returns_from_seed(seeded_db):
    result = zone_service.get_zone_restrictions("Victoria Avenue", seeded_db)
    assert "error" not in result
    assert result["street"].lower() == "victoria avenue"
    assert len(result["segments"]) >= 1


def test_zone_not_found(seeded_db):
    result = zone_service.get_zone_restrictions("Nonexistent Boulevard", seeded_db)
    assert result == {"error": "not_found"}


def test_victoria_avenue_case_insensitive(seeded_db):
    result = zone_service.get_zone_restrictions("victoria avenue", seeded_db)
    assert "error" not in result


def test_zone_segments_have_required_fields(seeded_db):
    result = zone_service.get_zone_restrictions("Victoria Avenue", seeded_db)
    for seg in result["segments"]:
        assert "rules_plain_english" in seg
        assert "rules_structured" in seg
        assert isinstance(seg["rules_structured"], list)


def test_zone_from_db_when_signs_loaded(seeded_db):
    # Insert two fake signs for "Albert Avenue" into the DB
    sign_cats = json.dumps([
        {"category": "No Stopping", "direction": "both", "description": "At all times"}
    ])
    with get_connection(seeded_db) as con:
        con.execute(
            "INSERT INTO parking_signs (lat, lon, street, raw_description, sign_categories) "
            "VALUES (-33.798, 151.183, 'Albert Avenue', 'raw', ?)",
            (sign_cats,),
        )
    result = zone_service.get_zone_restrictions("Albert Avenue", seeded_db)
    assert "error" not in result
    assert result["street"] == "Albert Avenue"
    assert len(result["segments"]) == 1
    assert "No Stopping" in result["segments"][0]["rules_plain_english"]


def test_signs_to_segments_groups_by_direction(seeded_db):
    sign_cats = json.dumps([
        {"category": "No Stopping", "direction": "left", "description": "7am-10am"},
        {"category": "Restricted Parking", "direction": "right", "description": "2P 10am-6pm"},
    ])
    with get_connection(seeded_db) as con:
        con.execute(
            "INSERT INTO parking_signs (lat, lon, street, raw_description, sign_categories) "
            "VALUES (-33.798, 151.183, 'Test Street', 'raw', ?)",
            (sign_cats,),
        )
    result = zone_service.get_zone_restrictions("Test Street", seeded_db)
    sides = {seg["side"] for seg in result["segments"]}
    assert "left" in sides
    assert "right" in sides
```

- [ ] **Step 3.2: Run tests — confirm they fail**

```bash
cd backend
pytest tests/test_zone_service.py -v
```

Expected: `ImportError: cannot import name 'zone_service' from 'app.services'`

- [ ] **Step 3.3: Create `backend/app/services/zone_service.py`**

```python
import json
import logging
from collections import defaultdict
from pathlib import Path

from app.db import get_connection
from app.models import RestrictionRule, ZoneResponse, ZoneSegment

log = logging.getLogger(__name__)

_SEED_PATH = Path(__file__).parent.parent / "data" / "seed_zones.json"
_seed_cache: dict | None = None


def _load_seed() -> dict:
    global _seed_cache
    if _seed_cache is None:
        _seed_cache = json.loads(_SEED_PATH.read_text())
    return _seed_cache


def get_zone_restrictions(street: str, db_path: Path) -> dict:
    """LLM tool 3: get_zone_restrictions. Returns ZoneResponse dict or {"error": "not_found"}."""
    # 1. Try DB (KML-sourced signs geocoded to this street)
    normalized = street.strip()
    with get_connection(db_path) as con:
        rows = con.execute(
            "SELECT sign_categories, sign_photo_url FROM parking_signs "
            "WHERE LOWER(street) = LOWER(?)",
            (normalized,),
        ).fetchall()

    if rows:
        segments = _signs_to_segments([dict(r) for r in rows])
        return ZoneResponse(street=normalized, segments=segments).model_dump()

    # 2. Fall back to seed_zones.json (keyed by normalized lowercase street name)
    seed = _load_seed()
    seed_key = normalized.lower().replace(" ", "_")
    if seed_key in seed:
        entry = seed[seed_key]
        segments = [
            ZoneSegment(
                side=seg.get("side"),
                rules_plain_english=seg["rules_plain_english"],
                rules_structured=[RestrictionRule(**r) for r in seg.get("rules_structured", [])],
                sign_photo_url=seg.get("sign_photo_url"),
            )
            for seg in entry["segments"]
        ]
        return ZoneResponse(street=entry["street"], segments=segments).model_dump()

    return {"error": "not_found"}


def _signs_to_segments(rows: list[dict]) -> list[ZoneSegment]:
    """Group DB sign rows into segments by direction."""
    groups: dict[str | None, list[dict]] = defaultdict(list)
    photo_by_side: dict[str | None, str | None] = {}

    for row in rows:
        entries = json.loads(row["sign_categories"])
        photo_url = row.get("sign_photo_url")
        for entry in entries:
            direction = entry.get("direction", "none")
            side: str | None = direction if direction in ("left", "right") else None
            groups[side].append(entry)
            if photo_url and side not in photo_by_side:
                photo_by_side[side] = photo_url

    segments = []
    for side, entries in groups.items():
        plain = ". ".join(
            f"{e['category']}: {e['description']}" for e in entries if e.get("description")
        )
        if not plain:
            plain = ". ".join(e["category"] for e in entries)
        segments.append(
            ZoneSegment(
                side=side,
                rules_plain_english=plain,
                rules_structured=[],
                sign_photo_url=photo_by_side.get(side),
            )
        )
    return segments
```

- [ ] **Step 3.4: Create `backend/app/routers/zones.py`**

```python
from fastapi import APIRouter, Depends, HTTPException, Query
from app.config import Settings, get_settings
from app.services import zone_service

router = APIRouter()


@router.get("/zones")
def get_zones(
    street: str = Query(..., description="Street name in Chatswood CBD"),
    settings: Settings = Depends(get_settings),
) -> dict:
    result = zone_service.get_zone_restrictions(street, settings.db_path)
    if "error" in result and result["error"] == "not_found":
        raise HTTPException(status_code=404, detail=f"No zone data found for '{street}'")
    return result
```

- [ ] **Step 3.5: Run tests — confirm they pass**

```bash
cd backend
pytest tests/test_zone_service.py -v
```

Expected: all 7 tests PASS.

---

## Task 4: `prediction_service.py` + `GET /api/predict`

**Files:**
- Create: `backend/app/services/prediction_service.py`
- Create: `backend/app/routers/predict.py`
- Create: `backend/tests/test_prediction_service.py`

**Context:** In Plan 2 the prediction service uses the simulator for every car park (both simulated and TfNSW). Plan 3 will swap TfNSW car parks to XGBoost. The `model_version` field signals which branch was used. `confidence` is flat 0.7 for all predictions in this plan.

- [ ] **Step 4.1: Write the failing tests**

Create `backend/tests/test_prediction_service.py`:

```python
import pytest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from app.config import Settings
from app.services import prediction_service


def _settings(seeded_db):
    return Settings(db_path=seeded_db, anthropic_api_key="")


# --- predict_availability_tool ---

def test_predict_sim_car_park(seeded_db):
    target = (datetime.now(timezone.utc) + timedelta(hours=3)).isoformat()
    result = prediction_service.predict_availability_tool("Westfield", target, seeded_db)
    assert "error" not in result
    assert result["car_park_id"] == "sim_westfield"
    assert 0.0 <= result["predicted_occupancy_pct"] <= 1.0
    assert result["confidence"] == 0.7
    assert result["model_version"] == "simulator-v1"


def test_predict_tfnsw_car_park(seeded_db):
    target = (datetime.now(timezone.utc) + timedelta(hours=3)).isoformat()
    result = prediction_service.predict_availability_tool("Gordon", target, seeded_db)
    assert "error" not in result
    assert result["car_park_id"] == "tfnsw_gordon"
    assert result["model_version"] == "simulator-v1"  # placeholder until Plan 3


def test_predict_out_of_range_future(seeded_db):
    target = (datetime.now(timezone.utc) + timedelta(days=8)).isoformat()
    result = prediction_service.predict_availability_tool("Westfield", target, seeded_db)
    assert result["error"] == "out_of_range"


def test_predict_rounds_to_nearest_hour(seeded_db):
    # 18:45 should be treated as 18:00
    base = datetime.now(timezone.utc).replace(hour=18, minute=45, second=0, microsecond=0)
    target = (base + timedelta(hours=1)).isoformat()
    result = prediction_service.predict_availability_tool("Westfield", target, seeded_db)
    assert "error" not in result
    dt_returned = result["target_datetime"]
    assert ":00:00" in dt_returned or dt_returned.endswith(":00")


def test_predict_no_match(seeded_db):
    target = (datetime.now(timezone.utc) + timedelta(hours=2)).isoformat()
    result = prediction_service.predict_availability_tool("NotAPlace XYZ", target, seeded_db)
    assert result["error"] == "no_match"
    assert "candidates" in result


def test_predict_invalid_datetime_returns_error(seeded_db):
    result = prediction_service.predict_availability_tool("Westfield", "not-a-datetime", seeded_db)
    assert result["error"] == "invalid_datetime"
```

- [ ] **Step 4.2: Run tests — confirm they fail**

```bash
cd backend
pytest tests/test_prediction_service.py -v
```

Expected: `ImportError: cannot import name 'prediction_service' from 'app.services'`

- [ ] **Step 4.3: Create `backend/app/services/prediction_service.py`**

```python
import logging
from datetime import datetime, timedelta, timezone
from pathlib import Path

from app.data.seed_car_parks import get_capacity
from app.models import PredictionResult
from app.services.occupancy_service import find_car_park
from app.services.simulator import simulated_available

log = logging.getLogger(__name__)

_MAX_FUTURE_DAYS = 7


def predict_availability_tool(
    location: str, target_datetime: str, db_path: Path
) -> dict:
    """LLM tool 2: predict_availability. Returns PredictionResult dict or error dict."""
    # Parse datetime
    try:
        target_dt = datetime.fromisoformat(target_datetime)
    except (ValueError, TypeError):
        return {"error": "invalid_datetime", "detail": f"Cannot parse '{target_datetime}' as ISO8601"}

    # Ensure timezone-aware for comparison
    if target_dt.tzinfo is None:
        target_dt = target_dt.replace(tzinfo=timezone.utc)

    now = datetime.now(timezone.utc)
    if target_dt > now + timedelta(days=_MAX_FUTURE_DAYS):
        return {
            "error": "out_of_range",
            "detail": f"target_datetime must be within {_MAX_FUTURE_DAYS} days of now",
        }

    # Round to the hour
    target_dt = target_dt.replace(minute=0, second=0, microsecond=0)

    # Resolve location to car park
    cp, candidates = find_car_park(location)
    if cp is None:
        return {"error": "no_match", "candidates": candidates}

    # Predict: use simulator for all car parks in Plan 2.
    # Plan 3 will swap TfNSW car parks to XGBoost here.
    capacity = get_capacity(cp.id)
    available = simulated_available(cp.id, target_dt)
    occupied = capacity - available
    predicted_pct = round(occupied / capacity, 4) if capacity > 0 else 0.0

    result = PredictionResult(
        car_park_id=cp.id,
        name=cp.name,
        predicted_occupancy_pct=predicted_pct,
        confidence=0.7,
        target_datetime=target_dt,
        model_version="simulator-v1",
    )
    return {
        **result.model_dump(),
        "target_datetime": target_dt.isoformat(),
    }
```

- [ ] **Step 4.4: Create `backend/app/routers/predict.py`**

```python
from fastapi import APIRouter, Depends, HTTPException, Query
from app.config import Settings, get_settings
from app.services import prediction_service

router = APIRouter()


@router.get("/predict")
def predict(
    location: str = Query(..., description="Car park name or nearby landmark"),
    target_datetime: str = Query(..., description="ISO8601 datetime, within next 7 days"),
    settings: Settings = Depends(get_settings),
) -> dict:
    result = prediction_service.predict_availability_tool(
        location, target_datetime, settings.db_path
    )
    if "error" in result:
        error = result["error"]
        if error == "no_match":
            raise HTTPException(status_code=404, detail=result)
        raise HTTPException(status_code=422, detail=result)
    return result
```

- [ ] **Step 4.5: Run tests — confirm they pass**

```bash
cd backend
pytest tests/test_prediction_service.py -v
```

Expected: all 6 tests PASS.

---

## Task 5: `llm_service.py` + `POST /api/chat`

**Files:**
- Create: `backend/app/services/llm_service.py`
- Create: `backend/app/routers/chat.py`
- Create: `backend/tests/test_llm_service.py`

**Context:** Uses `anthropic.AsyncAnthropic` so FastAPI can stream SSE natively from an async generator. Each API turn (non-streaming `messages.create`) is awaited; the generator yields JSON-encoded SSE data strings. Tool-call loop capped at 5 iterations. `_dispatch_tool` is synchronous — it calls pure-Python service functions directly.

- [ ] **Step 5.1: Write the failing tests**

Create `backend/tests/test_llm_service.py`:

```python
import json
import pytest
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch
from app.config import Settings
from app.services import llm_service


def _make_settings(seeded_db: Path) -> Settings:
    return Settings(db_path=seeded_db, anthropic_api_key="test-key")


def _text_response(text: str) -> MagicMock:
    block = MagicMock()
    block.type = "text"
    block.text = text
    resp = MagicMock()
    resp.content = [block]
    resp.stop_reason = "end_turn"
    return resp


def _tool_response(name: str, inputs: dict, tool_id: str = "toolu_01") -> MagicMock:
    block = MagicMock()
    block.type = "tool_use"
    block.name = name
    block.input = inputs
    block.id = tool_id
    resp = MagicMock()
    resp.content = [block]
    resp.stop_reason = "tool_use"
    return resp


# --- _dispatch_tool ---

def test_dispatch_get_live_occupancy(seeded_db):
    result = llm_service._dispatch_tool(
        "get_live_occupancy", {"location": "Westfield"}, seeded_db, _make_settings(seeded_db)
    )
    assert "error" not in result or result.get("error") == "no_match"
    if "error" not in result:
        assert "occupancy_pct" in result


def test_dispatch_get_zone_restrictions(seeded_db):
    result = llm_service._dispatch_tool(
        "get_zone_restrictions", {"street": "Victoria Avenue"}, seeded_db, _make_settings(seeded_db)
    )
    assert "street" in result or "error" in result


def test_dispatch_predict_availability(seeded_db):
    from datetime import datetime, timedelta, timezone
    target = (datetime.now(timezone.utc) + timedelta(hours=4)).isoformat()
    result = llm_service._dispatch_tool(
        "predict_availability",
        {"location": "Westfield", "target_datetime": target},
        seeded_db,
        _make_settings(seeded_db),
    )
    assert "predicted_occupancy_pct" in result or "error" in result


def test_dispatch_unknown_tool_returns_error(seeded_db):
    result = llm_service._dispatch_tool(
        "fly_to_moon", {"destination": "moon"}, seeded_db, _make_settings(seeded_db)
    )
    assert result["error"] == "unknown_tool"


# --- chat_stream ---

@pytest.mark.asyncio
async def test_chat_stream_no_tool_call(seeded_db):
    settings = _make_settings(seeded_db)
    mock_resp = _text_response("Westfield has 392 spots available.")

    with patch("app.services.llm_service.anthropic.AsyncAnthropic") as MockAnth:
        instance = MockAnth.return_value
        instance.messages.create = AsyncMock(return_value=mock_resp)

        chunks = []
        async for chunk in llm_service.chat_stream("Where to park?", [], seeded_db, settings):
            chunks.append(json.loads(chunk))

    types = [c["type"] for c in chunks]
    assert "text" in types
    assert "done" in types


@pytest.mark.asyncio
async def test_chat_stream_one_tool_call_then_text(seeded_db):
    settings = _make_settings(seeded_db)
    tool_resp = _tool_response("get_live_occupancy", {"location": "Westfield"})
    text_resp = _text_response("Westfield is 72% full.")

    with patch("app.services.llm_service.anthropic.AsyncAnthropic") as MockAnth:
        instance = MockAnth.return_value
        instance.messages.create = AsyncMock(side_effect=[tool_resp, text_resp])

        chunks = []
        async for chunk in llm_service.chat_stream("Where to park?", [], seeded_db, settings):
            chunks.append(json.loads(chunk))

    types = [c["type"] for c in chunks]
    assert "tool_call" in types
    assert "tool_result" in types
    assert "text" in types
    assert "done" in types


@pytest.mark.asyncio
async def test_chat_stream_stops_after_max_iterations(seeded_db):
    settings = _make_settings(seeded_db)
    always_tool = _tool_response("get_live_occupancy", {"location": "Westfield"})

    with patch("app.services.llm_service.anthropic.AsyncAnthropic") as MockAnth:
        instance = MockAnth.return_value
        instance.messages.create = AsyncMock(return_value=always_tool)

        chunks = []
        async for chunk in llm_service.chat_stream("Hello", [], seeded_db, settings):
            chunks.append(json.loads(chunk))

    assert chunks[-1]["type"] == "done"
    tool_calls = [c for c in chunks if c["type"] == "tool_call"]
    assert len(tool_calls) == llm_service.MAX_TOOL_ITERATIONS
```

- [ ] **Step 5.2: Run tests — confirm they fail**

```bash
cd backend
pytest tests/test_llm_service.py -v
```

Expected: `ImportError: cannot import name 'llm_service' from 'app.services'`

- [ ] **Step 5.3: Create `backend/app/services/llm_service.py`**

```python
import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import AsyncIterator

import anthropic

from app.config import Settings
from app.services import occupancy_service, prediction_service, zone_service

log = logging.getLogger(__name__)

MAX_TOOL_ITERATIONS = 5
_MODEL = "claude-haiku-4-5-20251001"

SYSTEM_PROMPT = """\
You are ParkSmart, a helpful parking assistant for Chatswood CBD, Sydney, Australia.

You have three tools:
- get_live_occupancy(location): Current occupancy for a car park near a location or landmark.
- predict_availability(location, target_datetime): Predicted occupancy at a future time (up to 7 days). Use only when the user mentions a specific future time.
- get_zone_restrictions(street): Parking time rules for a street in Chatswood.

Behaviour rules:
- For "where to park" queries: call get_live_occupancy first. Then predict_availability only if the user mentions a future time.
- For "parking rules on X" queries: call get_zone_restrictions directly.
- If a tool returns {{"error": "no_match", "candidates": [...]}}, pick the closest candidate name and retry.
- Simulated car parks use pattern-based estimates — label them clearly as "estimated".
- Be concise and practical. Mention walking distance context when recommending a car park.
- Today is {date}. Sydney time is AEST (UTC+10) or AEDT (UTC+11) during daylight saving.\
"""

TOOLS: list[dict] = [
    {
        "name": "get_live_occupancy",
        "description": (
            "Get current parking occupancy for a car park in Chatswood CBD. "
            "Returns occupancy percentage, available spots, and whether the data is "
            "live (from TfNSW sensors) or estimated."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "location": {
                    "type": "string",
                    "description": "Car park name or nearby landmark (e.g. 'Westfield', 'Mandarin Centre', 'Victoria Avenue')",
                }
            },
            "required": ["location"],
        },
    },
    {
        "name": "predict_availability",
        "description": (
            "Predict parking availability at a specific future time (up to 7 days ahead). "
            "Use this only when the user mentions a future time, not for current conditions."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "location": {
                    "type": "string",
                    "description": "Car park name or nearby landmark in Chatswood",
                },
                "target_datetime": {
                    "type": "string",
                    "description": "ISO 8601 datetime string, e.g. '2026-05-15T18:00:00'. Must be within 7 days.",
                },
            },
            "required": ["location", "target_datetime"],
        },
    },
    {
        "name": "get_zone_restrictions",
        "description": (
            "Get street parking time restrictions for a street in Chatswood CBD. "
            "Returns no-stopping zones, timed parking limits, and permit areas."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "street": {
                    "type": "string",
                    "description": "Street name in Chatswood CBD, e.g. 'Victoria Avenue', 'Albert Avenue'",
                }
            },
            "required": ["street"],
        },
    },
]


def _dispatch_tool(name: str, inputs: dict, db_path: Path, settings: Settings) -> dict:
    """Call the matching service function and return a JSON-serialisable dict."""
    try:
        if name == "get_live_occupancy":
            return occupancy_service.get_live_occupancy_tool(
                inputs["location"], db_path, settings
            )
        if name == "predict_availability":
            return prediction_service.predict_availability_tool(
                inputs["location"], inputs["target_datetime"], db_path
            )
        if name == "get_zone_restrictions":
            return zone_service.get_zone_restrictions(inputs["street"], db_path)
        return {"error": "unknown_tool", "tool": name}
    except Exception as exc:
        log.error("Tool dispatch error for '%s': %s", name, exc)
        return {"error": "tool_error", "detail": str(exc)}


async def chat_stream(
    message: str,
    history: list[dict],
    db_path: Path,
    settings: Settings,
) -> AsyncIterator[str]:
    """
    Async generator yielding JSON-encoded SSE data strings.
    Each string is one of:
      {"type": "text",        "content": str}
      {"type": "tool_call",   "tool": str, "input": dict}
      {"type": "tool_result", "tool": str, "result": dict}
      {"type": "done"}
    """
    client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)
    messages = list(history) + [{"role": "user", "content": message}]
    system = SYSTEM_PROMPT.format(date=datetime.now(timezone.utc).strftime("%Y-%m-%d"))

    for _ in range(MAX_TOOL_ITERATIONS):
        response = await client.messages.create(
            model=_MODEL,
            max_tokens=1024,
            system=system,
            tools=TOOLS,
            messages=messages,
        )

        for block in response.content:
            if block.type == "text":
                yield json.dumps({"type": "text", "content": block.text})

        if response.stop_reason != "tool_use":
            break

        tool_results = []
        for block in response.content:
            if block.type != "tool_use":
                continue
            yield json.dumps({"type": "tool_call", "tool": block.name, "input": block.input})
            result = _dispatch_tool(block.name, block.input, db_path, settings)
            yield json.dumps({"type": "tool_result", "tool": block.name, "result": result})
            tool_results.append(
                {
                    "type": "tool_result",
                    "tool_use_id": block.id,
                    "content": json.dumps(result),
                }
            )

        messages = messages + [
            {"role": "assistant", "content": response.content},
            {"role": "user", "content": tool_results},
        ]

    yield json.dumps({"type": "done"})
```

- [ ] **Step 5.4: Create `backend/app/routers/chat.py`**

```python
from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from app.config import Settings, get_settings
from app.models import ChatRequest
from app.services import llm_service

router = APIRouter()


@router.post("/chat")
async def chat(
    request: ChatRequest,
    settings: Settings = Depends(get_settings),
) -> StreamingResponse:
    async def event_stream():
        async for chunk in llm_service.chat_stream(
            request.message, request.history, settings.db_path, settings
        ):
            yield f"data: {chunk}\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream")
```

- [ ] **Step 5.5: Run tests — confirm they pass**

```bash
cd backend
pytest tests/test_llm_service.py -v
```

Expected: all 7 tests PASS.

---

## Task 6: Scheduler + update `main.py` + integration tests

**Files:**
- Create: `backend/app/scheduler.py`
- Modify: `backend/app/main.py`
- Create: `backend/tests/test_api.py`

- [ ] **Step 6.1: Create `backend/app/scheduler.py`**

```python
import logging
from pathlib import Path

from apscheduler.schedulers.background import BackgroundScheduler

from app.config import Settings
from app.services import occupancy_service

log = logging.getLogger(__name__)


def create_scheduler(db_path: Path, settings: Settings) -> BackgroundScheduler:
    scheduler = BackgroundScheduler()

    scheduler.add_job(
        func=occupancy_service.refresh_tfnsw,
        trigger="interval",
        seconds=300,       # every 5 minutes
        id="tfnsw_poll",
        kwargs={"db_path": db_path, "settings": settings},
        replace_existing=True,
    )

    scheduler.add_job(
        func=occupancy_service.refresh_sim,
        trigger="interval",
        seconds=3600,      # every 1 hour
        id="sim_refresh",
        kwargs={"db_path": db_path},
        replace_existing=True,
    )

    return scheduler
```

- [ ] **Step 6.2: Replace `backend/app/main.py` with the full version**

```python
import json
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.data.kml_loader import parse_kml
from app.data.seed_car_parks import seed as seed_car_parks
from app.db import get_connection, init_db
from app.scheduler import create_scheduler
from app.services.occupancy_service import backfill_sim_history

log = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")

_scheduler = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _scheduler
    log.info("Starting ParkSmart backend")

    # 1. Bootstrap database
    init_db(settings.db_path)
    log.info("Database ready at %s", settings.db_path)

    # 2. Seed car parks (idempotent)
    seed_car_parks(settings.db_path)
    log.info("Car parks seeded")

    # 3. Parse KML (if file exists)
    kml_path = settings.fixtures_dir.parent / "willoughby_parking.kml"
    if kml_path.exists():
        signs = parse_kml(kml_path, geocode=True)
        with get_connection(settings.db_path) as con:
            con.executemany(
                """
                INSERT OR IGNORE INTO parking_signs
                    (raw_sign_id, lat, lon, street, raw_description, sign_categories, sign_photo_url)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    (
                        s.raw_sign_id,
                        s.lat, s.lon, s.street, s.raw_description,
                        json.dumps([e.model_dump() for e in s.signs]),
                        s.sign_photo_url,
                    )
                    for s in signs
                ],
            )
        log.info("Loaded %d parking signs", len(signs))
    else:
        log.warning("KML file not found at %s — skipping sign load", kml_path)

    # 4. Backfill 90 days of simulated history (idempotent — INSERT OR IGNORE)
    backfill_sim_history(settings.db_path, days=90)
    log.info("Sim history backfill complete")

    # 5. Start background scheduler
    _scheduler = create_scheduler(settings.db_path, settings)
    _scheduler.start()
    log.info("Scheduler started")

    yield

    if _scheduler and _scheduler.running:
        _scheduler.shutdown(wait=False)
    log.info("Shutting down ParkSmart backend")


app = FastAPI(title="ParkSmart API", version="0.2.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],    # restrict in production
    allow_methods=["*"],
    allow_headers=["*"],
)

from app.routers import occupancy, zones, predict, chat  # noqa: E402

app.include_router(occupancy.router, prefix="/api")
app.include_router(zones.router, prefix="/api")
app.include_router(predict.router, prefix="/api")
app.include_router(chat.router, prefix="/api")


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}
```

- [ ] **Step 6.3: Write the failing integration tests**

Create `backend/tests/test_api.py`:

```python
import json
import pytest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from fastapi.testclient import TestClient
from app.config import Settings, get_settings
from app.main import app
from app.services.occupancy_service import backfill_sim_history


@pytest.fixture
def test_settings(seeded_db: Path) -> Settings:
    return Settings(
        db_path=seeded_db,
        tfnsw_api_key="",
        anthropic_api_key="test",
        fixtures_dir=Path("data_raw/tfnsw_fixtures"),
    )


@pytest.fixture
def client(test_settings: Settings):
    app.dependency_overrides[get_settings] = lambda: test_settings
    yield TestClient(app, raise_server_exceptions=True)
    app.dependency_overrides.clear()


# --- health ---

def test_health(client):
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


# --- /api/occupancy ---

def test_occupancy_returns_list(client):
    resp = client.get("/api/occupancy")
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)
    assert len(data) == 7


def test_occupancy_response_shape(client):
    resp = client.get("/api/occupancy")
    for item in resp.json():
        assert "car_park_id" in item
        assert "occupancy_pct" in item
        assert "lat" in item
        assert "lon" in item
        assert item["source"] in ("tfnsw", "simulated")


# --- /api/zones ---

def test_zones_victoria_avenue(client):
    resp = client.get("/api/zones", params={"street": "Victoria Avenue"})
    assert resp.status_code == 200
    data = resp.json()
    assert "street" in data
    assert len(data["segments"]) >= 1


def test_zones_not_found(client):
    resp = client.get("/api/zones", params={"street": "Imaginary Boulevard"})
    assert resp.status_code == 404


# --- /api/predict ---

def test_predict_returns_result(client):
    target = (datetime.now(timezone.utc) + timedelta(hours=5)).isoformat()
    resp = client.get("/api/predict", params={"location": "Westfield", "target_datetime": target})
    assert resp.status_code == 200
    data = resp.json()
    assert "predicted_occupancy_pct" in data
    assert "model_version" in data


def test_predict_out_of_range(client):
    target = (datetime.now(timezone.utc) + timedelta(days=10)).isoformat()
    resp = client.get("/api/predict", params={"location": "Westfield", "target_datetime": target})
    assert resp.status_code == 422


def test_predict_unknown_location(client):
    target = (datetime.now(timezone.utc) + timedelta(hours=2)).isoformat()
    resp = client.get("/api/predict", params={"location": "NotARealPlace XYZ", "target_datetime": target})
    assert resp.status_code == 404
```

- [ ] **Step 6.4: Run tests — confirm they fail**

```bash
cd backend
pytest tests/test_api.py -v
```

Expected: import errors or test failures (routers not mounted yet at this point in execution — but if you followed the tasks in order, the app is already complete and they should pass).

- [ ] **Step 6.5: Verify scheduler jobs are registered**

Create a quick sanity check (not a committed test — run and discard):

```bash
cd backend
python3 -c "
from pathlib import Path
from app.config import Settings
from app.scheduler import create_scheduler

s = Settings(db_path=Path('/tmp/test.db'))
sched = create_scheduler(Path('/tmp/test.db'), s)
for job in sched.get_jobs():
    print(job.id, job.trigger)
"
```

Expected output (order may vary):
```
tfnsw_poll <IntervalTrigger (interval=0:05:00, ...)>
sim_refresh <IntervalTrigger (interval=1:00:00, ...)>
```

- [ ] **Step 6.6: Run the full API integration tests**

```bash
cd backend
pytest tests/test_api.py -v
```

Expected: all 9 tests PASS.

- [ ] **Step 6.7: Run the complete test suite**

```bash
cd backend
pytest -v --tb=short
```

Expected: all tests PASS (from Plans 1 and 2 combined).

- [ ] **Step 6.8: Start the server and smoke-test all endpoints**

```bash
cd backend
uvicorn app.main:app --reload
```

In a second terminal:

```bash
# Health
curl http://localhost:8000/health

# All car parks
curl http://localhost:8000/api/occupancy | python3 -m json.tool | head -30

# Victoria Avenue zones
curl "http://localhost:8000/api/zones?street=Victoria+Avenue" | python3 -m json.tool

# Predict
TARGET=$(python3 -c "from datetime import datetime,timedelta,timezone; print((datetime.now(timezone.utc)+timedelta(hours=4)).isoformat())")
curl "http://localhost:8000/api/predict?location=Westfield&target_datetime=$TARGET" | python3 -m json.tool

# Chat (SSE) — Ctrl-C to stop streaming
curl -N -X POST http://localhost:8000/api/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "Where should I park near Westfield Chatswood right now?", "history": []}' \
  | head -20
```

Expected for each:
- `/health` → `{"status": "ok"}`
- `/api/occupancy` → JSON array of 7 car parks
- `/api/zones?street=Victoria+Avenue` → segments with rules
- `/api/predict` → `predicted_occupancy_pct`, `model_version: "simulator-v1"`
- `/api/chat` → `data: {...}` SSE lines (requires `ANTHROPIC_API_KEY` in `.env`)

---

## Self-Review

### 1. Spec coverage

| Spec requirement | Covered by |
|---|---|
| `get_live_occupancy` LLM tool | Task 2 `occupancy_service.get_live_occupancy_tool` |
| `predict_availability` LLM tool | Task 4 `prediction_service.predict_availability_tool` |
| `get_zone_restrictions` LLM tool | Task 3 `zone_service.get_zone_restrictions` |
| Occupancy map API | Task 2 `GET /api/occupancy` |
| Zone restrictions API | Task 3 `GET /api/zones` |
| Prediction API | Task 4 `GET /api/predict` |
| LLM chat + SSE stream | Task 5 `POST /api/chat` |
| Tool-call loop capped at 5 | Task 5 `MAX_TOOL_ITERATIONS = 5` |
| Tool error → candidates list for recovery | Tasks 2 + 4 `"candidates"` key |
| `{"error": "no_match", "candidates": [...]}` contract | Tasks 2 + 4 |
| `{"error": "out_of_range"}` contract | Task 4 |
| APScheduler 5-min TfNSW poll | Task 6 `create_scheduler` |
| APScheduler 1-hour sim refresh | Task 6 `create_scheduler` |
| 90-day sim history backfill on startup | Task 6 `main.py` lifespan |
| occupancy_service hides real/simulated split | Task 2 `get_all_occupancy` |
| prediction_service routes by source | Task 4 (sim-only in Plan 2; Plan 3 adds XGBoost) |
| CORS for frontend | Task 6 `CORSMiddleware` |
| `model_version` field in predictions | Task 4 `"simulator-v1"` |
| System prompt pinning tool-call patterns | Task 5 `SYSTEM_PROMPT` |
| Few-shot examples in prompt | Task 5 (guidelines listed; full few-shot is Plan 2's stretch goal — see below) |
| XGBoost ML branch for TfNSW car parks | **Plan 3** |

**Gap:** The spec mentions few-shot examples for each demo scenario in the system prompt. The current `SYSTEM_PROMPT` has guidelines but not literal few-shot examples. Adding them is low-risk (edit the string constant) and should be done after Plan 3 when the exact tool response shapes are confirmed from real data.

### 2. Placeholder scan

None found. All steps contain complete code.

### 3. Type consistency

- `OccupancyResponse` defined in Task 1 (models.py), returned by `get_all_occupancy` (Task 2), used in router (Task 2). ✓
- `ZoneSegment` / `ZoneResponse` defined in Task 1, used in `zone_service` (Task 3) and router (Task 3). ✓
- `ChatRequest` defined in Task 1, used in `chat.py` router (Task 5). ✓
- `find_car_park(location: str) -> tuple[CarPark | None, list[str]]` — same signature in `occupancy_service` (Task 2) and imported by `prediction_service` (Task 4). ✓
- `_dispatch_tool(name, inputs, db_path, settings) -> dict` — signature matches calls in `chat_stream` (Task 5). ✓
- `create_scheduler(db_path, settings) -> BackgroundScheduler` — defined in Task 6, called in `main.py` (Task 6). ✓
- `backfill_sim_history(db_path, days=90)` — defined in Task 2, called in `main.py` lifespan (Task 6). ✓
- `refresh_tfnsw(db_path, settings)` / `refresh_sim(db_path, dt=None)` — signatures match scheduler job `kwargs` in Task 6. ✓
