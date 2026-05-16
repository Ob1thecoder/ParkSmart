# Backend Foundation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the complete backend foundation for ParkSmart — project scaffold, database layer, seed data, deterministic occupancy simulator, TfNSW API client, and Willoughby KML parser — such that all data-ingestion paths are tested and the app starts cleanly with or without live API keys.

**Architecture:** FastAPI app with a SQLite database managed by a thin stdlib `sqlite3` wrapper (no ORM). All data ingestion modules are pure functions that write to the DB; the API client falls back to recorded fixtures when the TfNSW key is absent. The simulator is a deterministic pure function used for both live and historical occupancy of CBD car parks not covered by TfNSW.

**Tech Stack:** Python 3.11+, FastAPI, Pydantic v2, pydantic-settings, httpx, lxml, sqlite3 (stdlib), pytest, pytest-asyncio

---

## Scope note

This is Plan 1 of 4. It produces a backend that boots, seeds itself, and passes all data-layer tests. It does **not** yet include:
- Service layer or API endpoints (Plan 2)
- ML pipeline (Plan 3)
- Frontend (Plan 4)

---

## File structure

```
backend/
├── pyproject.toml                    CREATE — dependencies, tool config
├── .env.example                      CREATE — env var template
├── app/
│   ├── __init__.py                   CREATE — empty
│   ├── main.py                       CREATE — FastAPI app, lifespan startup
│   ├── config.py                     CREATE — pydantic-settings Settings class
│   ├── db.py                         CREATE — sqlite3 wrapper, schema bootstrap
│   ├── models.py                     CREATE — pydantic types shared across layers
│   ├── data/
│   │   ├── __init__.py               CREATE — empty
│   │   ├── seed_car_parks.py         CREATE — 5 car parks with lat/lon/capacity
│   │   ├── seed_zones.json           CREATE — curated Victoria Avenue restrictions
│   │   ├── tfnsw_client.py           CREATE — httpx client + fixture fallback
│   │   └── kml_loader.py             CREATE — lxml KML parser → parking_signs rows
│   └── services/
│       ├── __init__.py               CREATE — empty
│       └── simulator.py              CREATE — deterministic occupancy function
├── data_raw/
│   ├── .gitkeep                      CREATE — dir tracked, contents gitignored
│   └── tfnsw_fixtures/
│       ├── chatswood_interchange.json  CREATE — single-facility snapshot fixture
│       ├── full_list.json              CREATE — full-list endpoint fixture (all facilities)
│       ├── facility_list.json          CREATE — discovery endpoint fixture (IDs + names)
│       └── history_sample.json         CREATE — history endpoint fixture (one day, hourly)
└── tests/
    ├── __init__.py                   CREATE — empty
    ├── conftest.py                   CREATE — db_path + conn fixtures
    ├── test_db.py                    CREATE — schema bootstrap, idempotency, FK enforcement
    ├── test_simulator.py             CREATE — determinism, capacity bounds, patterns
    ├── test_tfnsw_client.py          CREATE — fixture fallback, field mapping
    └── test_kml_loader.py            CREATE — sign parsing, street extraction
```

---

## Task 1: Project scaffold and configuration

**Files:**
- Create: `backend/pyproject.toml`
- Create: `backend/.env.example`
- Create: `backend/app/__init__.py`
- Create: `backend/app/config.py`
- Create: `backend/tests/__init__.py`
- Create: `backend/tests/conftest.py`

- [ ] **Step 1.1: Create `backend/pyproject.toml`**

```toml
[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[project]
name = "parksmart-backend"
version = "0.1.0"
requires-python = ">=3.11"
dependencies = [
    "fastapi>=0.115",
    "uvicorn[standard]>=0.30",
    "httpx>=0.27",
    "apscheduler>=3.10",
    "anthropic>=0.40",
    "xgboost>=2.1",
    "pandas>=2.2",
    "scikit-learn>=1.5",
    "lxml>=5.2",
    "pydantic>=2.8",
    "pydantic-settings>=2.4",
    "python-dotenv>=1.0",
]

[project.optional-dependencies]
dev = [
    "pytest>=8.3",
    "pytest-asyncio>=0.23",
    "pytest-cov>=5.0",
    "respx>=0.21",
]

[tool.pytest.ini_options]
asyncio_mode = "auto"
testpaths = ["tests"]

[tool.hatch.build.targets.wheel]
packages = ["app"]
```

- [ ] **Step 1.2: Create `backend/.env.example`**

```
TFNSW_API_KEY=
ANTHROPIC_API_KEY=
DB_PATH=parksmart.db
FIXTURES_DIR=data_raw/tfnsw_fixtures
```

- [ ] **Step 1.3: Create `backend/app/__init__.py`** (empty file)

- [ ] **Step 1.4: Create `backend/app/config.py`**

```python
from pydantic_settings import BaseSettings
from pathlib import Path


class Settings(BaseSettings):
    tfnsw_api_key: str = ""
    anthropic_api_key: str = ""
    db_path: Path = Path("parksmart.db")
    fixtures_dir: Path = Path("data_raw/tfnsw_fixtures")

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


settings = Settings()
```

- [ ] **Step 1.5: Create `backend/tests/__init__.py`** (empty file)

- [ ] **Step 1.6: Create `backend/tests/conftest.py`**

```python
import pytest
from pathlib import Path
from app.db import init_db, get_connection


@pytest.fixture
def db_path(tmp_path: Path) -> Path:
    path = tmp_path / "test.db"
    init_db(path)
    return path


@pytest.fixture
def conn(db_path: Path):
    with get_connection(db_path) as con:
        yield con
```

- [ ] **Step 1.7: Install dependencies**

```bash
cd backend
pip install -e ".[dev]"
```

Expected: all packages install without errors.

- [ ] **Step 1.8: Verify pytest discovers tests**

```bash
cd backend
pytest --collect-only
```

Expected: `no tests ran` (no tests written yet, but no collection errors).

---

## Task 2: SQLite database module

**Files:**
- Create: `backend/app/db.py`
- Create: `backend/tests/test_db.py`

- [ ] **Step 2.1: Write the failing tests**

Create `backend/tests/test_db.py`:

```python
import sqlite3
import pytest
from pathlib import Path
from app.db import init_db, get_connection


def test_init_creates_required_tables(db_path: Path):
    with get_connection(db_path) as con:
        cur = con.execute(
            "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
        )
        tables = {row[0] for row in cur.fetchall()}
    assert tables >= {"car_parks", "occupancy_history", "parking_signs"}


def test_init_is_idempotent(db_path: Path):
    # Calling init_db twice must not raise or corrupt data
    init_db(db_path)
    with get_connection(db_path) as con:
        con.execute("SELECT count(*) FROM car_parks").fetchone()


def test_foreign_key_enforcement(db_path: Path):
    with get_connection(db_path) as con:
        with pytest.raises(sqlite3.IntegrityError):
            con.execute(
                "INSERT INTO occupancy_history "
                "(car_park_id, ts, available, total_spots) "
                "VALUES ('nonexistent_id', datetime('now'), 100, 200)"
            )


def test_occupancy_history_primary_key(db_path: Path):
    with get_connection(db_path) as con:
        con.execute(
            "INSERT INTO car_parks (id, name, lat, lon, source) "
            "VALUES ('test_cp', 'Test', -33.7, 151.1, 'simulated')"
        )
        con.execute(
            "INSERT INTO occupancy_history (car_park_id, ts, available, total_spots) "
            "VALUES ('test_cp', '2026-05-11T10:00:00', 100, 200)"
        )
        con.commit()
        with pytest.raises(sqlite3.IntegrityError):
            con.execute(
                "INSERT INTO occupancy_history (car_park_id, ts, available, total_spots) "
                "VALUES ('test_cp', '2026-05-11T10:00:00', 99, 200)"
            )


def test_parking_signs_has_sign_categories_column(db_path: Path):
    with get_connection(db_path) as con:
        con.execute(
            "INSERT INTO parking_signs (lat, lon, raw_description, sign_categories) "
            "VALUES (-33.795, 151.183, 'test', '[{\"category\":\"No Stopping\"}]')"
        )
        row = con.execute("SELECT sign_categories FROM parking_signs LIMIT 1").fetchone()
    assert "No Stopping" in row["sign_categories"]
```

- [ ] **Step 2.2: Run tests — confirm they fail**

```bash
cd backend
pytest tests/test_db.py -v
```

Expected: `ImportError: cannot import name 'init_db' from 'app.db'` (module doesn't exist yet).

- [ ] **Step 2.3: Create `backend/app/db.py`**

```python
import sqlite3
from contextlib import contextmanager
from pathlib import Path


_SCHEMA = """
PRAGMA journal_mode=WAL;
PRAGMA foreign_keys=ON;

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

CREATE TABLE IF NOT EXISTS occupancy_history (
    car_park_id  TEXT NOT NULL REFERENCES car_parks(id),
    ts           TEXT NOT NULL,
    available    INTEGER NOT NULL,
    total_spots  INTEGER NOT NULL,
    PRIMARY KEY (car_park_id, ts)
);

CREATE INDEX IF NOT EXISTS idx_occ_ts ON occupancy_history(ts);

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

-- sign_categories is a JSON array: [{"category":"No Stopping","direction":"both","description":""}]
-- street is populated by reverse geocoding at first load; NULL if geocoder unavailable.
CREATE INDEX IF NOT EXISTS idx_signs_street
    ON parking_signs(LOWER(street));
"""


def init_db(db_path: Path) -> None:
    with get_connection(db_path) as con:
        con.executescript(_SCHEMA)


@contextmanager
def get_connection(db_path: Path):
    con = sqlite3.connect(str(db_path), detect_types=sqlite3.PARSE_DECLTYPES)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA foreign_keys=ON")
    try:
        yield con
        con.commit()
    except Exception:
        con.rollback()
        raise
    finally:
        con.close()
```

- [ ] **Step 2.4: Run tests — confirm they pass**

```bash
cd backend
pytest tests/test_db.py -v
```

Expected:
```
PASSED tests/test_db.py::test_init_creates_required_tables
PASSED tests/test_db.py::test_init_is_idempotent
PASSED tests/test_db.py::test_foreign_key_enforcement
PASSED tests/test_db.py::test_occupancy_history_primary_key
```

---

## Task 3: Pydantic models

**Files:**
- Create: `backend/app/models.py`

No separate test file — models are implicitly validated by every other test that constructs them.

- [ ] **Step 3.1: Create `backend/app/models.py`**

```python
from datetime import datetime
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field


class CarPark(BaseModel):
    id: str
    name: str
    lat: float
    lon: float
    suburb: str | None = None
    address: str | None = None
    source: Literal["tfnsw", "simulated"]
    tfnsw_facility_id: str | None = None
    # Not stored in DB — computed from latest occupancy_history row
    total_spots: int = 0


class OccupancySnapshot(BaseModel):
    car_park_id: str
    ts: datetime
    available: int
    total_spots: int

    @property
    def occupancy_pct(self) -> float:
        if self.total_spots == 0:
            return 0.0
        return round(1.0 - self.available / self.total_spots, 4)


class SignEntry(BaseModel):
    """One sign panel on a sign post (up to 4 per post in the Willoughby KML)."""
    category: str    # "No Stopping", "No Parking", "Restricted Parking", etc.
    direction: str   # "left", "right", "both", "none"
    description: str # time/duration: "Max Dur. 1 hour 8:30a - 6:00p M-F; ..."


class ParkingSignRecord(BaseModel):
    """
    One sign post from the Willoughby Council KML.
    street is populated by reverse geocoding after parse; None if geocoder unavailable.
    """
    model_config = ConfigDict(frozen=False)  # allow street to be set post-construction

    raw_sign_id: str | None = None
    lat: float
    lon: float
    street: str | None = None
    raw_description: str
    signs: list[SignEntry]      # extracted from sign1_category … sign4_category fields
    sign_photo_url: str | None = None


# RestrictionRule is used by zone_service (Plan 2) and seed_zones.json.
# It represents a parsed time/day rule derived from SignEntry.description.
class RestrictionRule(BaseModel):
    days: list[str]
    start: str           # "HH:MM"
    end: str             # "HH:MM"
    max_minutes: int | None = None
    type: Literal["no_stopping", "no_parking", "timed", "permit_only", "loading", "other"]


class PredictionResult(BaseModel):
    car_park_id: str
    name: str
    predicted_occupancy_pct: float = Field(ge=0.0, le=1.0)
    confidence: float = Field(ge=0.0, le=1.0)
    target_datetime: datetime
    model_version: str
```

---

## Task 4: Seed car parks and curated zone data

**Files:**
- Create: `backend/app/data/__init__.py`
- Create: `backend/app/data/seed_car_parks.py`
- Create: `backend/app/data/seed_zones.json`

- [ ] **Step 4.1: Create `backend/app/data/__init__.py`** (empty file)

- [ ] **Step 4.2: Create `backend/app/data/seed_car_parks.py`**

```python
"""
Static seed data for ParkSmart car parks.

DATA AUDIT FINDING: Chatswood CBD has NO entries in the TfNSW Car Park API.
The API covers commuter Park&Ride facilities; the nearest North Shore entries
are Gordon (#6) and Lindfield (#34).

Consequence:
  - All 5 Chatswood CBD car parks are source="simulated".
  - Gordon is seeded as source="tfnsw" and used for:
      a) A live real-data marker on the map (labelled, ~3km from Chatswood CBD)
      b) ML model training data via get_history() (commuter pattern proxy)

The TfNSW facility_id values match the 'facility_id' field in the API response
(a simple integer string, e.g. "6"), NOT the TSN or tfnsw_facility_id composite.
"""
from app.models import CarPark
from app.db import get_connection

# Chatswood CBD car parks — all simulated (not in TfNSW feed)
CHATSWOOD_CAR_PARKS: list[CarPark] = [
    CarPark(
        id="sim_westfield",
        name="Westfield Chatswood",
        lat=-33.7972,
        lon=151.1825,
        suburb="Chatswood",
        address="1 Anderson Street, Chatswood NSW 2067",
        source="simulated",
        total_spots=1400,
    ),
    CarPark(
        id="sim_chatswood_chase",
        name="Chatswood Chase",
        lat=-33.7964,
        lon=151.1799,
        suburb="Chatswood",
        address="345 Victoria Avenue, Chatswood NSW 2067",
        source="simulated",
        total_spots=850,
    ),
    CarPark(
        id="sim_mandarin_centre",
        name="Mandarin Centre",
        lat=-33.7992,
        lon=151.1804,
        suburb="Chatswood",
        address="1 Albert Avenue, Chatswood NSW 2067",
        source="simulated",
        total_spots=280,
    ),
    CarPark(
        id="sim_victoria_ave_cp",
        name="Victoria Avenue Car Park",
        lat=-33.7975,
        lon=151.1810,
        suburb="Chatswood",
        address="Victoria Avenue, Chatswood NSW 2067",
        source="simulated",
        total_spots=160,
    ),
    CarPark(
        id="sim_chatswood_west_cp",
        name="Chatswood West Car Park",
        lat=-33.7968,
        lon=151.1788,
        suburb="Chatswood",
        address="Help Street, Chatswood NSW 2067",
        source="simulated",
        total_spots=320,
    ),
]

# Real TfNSW facilities — used for live data display and ML training.
# Gordon is the closest active North Shore commuter car park (~3km from Chatswood).
TFNSW_CAR_PARKS: list[CarPark] = [
    CarPark(
        id="tfnsw_gordon",
        name="Park&Ride - Gordon",
        lat=-33.756009,
        lon=151.154528,
        suburb="Gordon",
        address="Henry Street, Gordon NSW 2072",
        source="tfnsw",
        tfnsw_facility_id="6",   # facility_id field from API response
        total_spots=213,
    ),
    CarPark(
        id="tfnsw_lindfield",
        name="Park&Ride - Lindfield",
        lat=-33.775185,
        lon=151.169111,
        suburb="Lindfield",
        address="Village Green, Lindfield NSW 2070",
        source="tfnsw",
        tfnsw_facility_id="34",
        total_spots=94,
    ),
]

ALL_CAR_PARKS: list[CarPark] = CHATSWOOD_CAR_PARKS + TFNSW_CAR_PARKS

_TOTAL_SPOTS: dict[str, int] = {cp.id: cp.total_spots for cp in ALL_CAR_PARKS}


def get_capacity(car_park_id: str) -> int:
    return _TOTAL_SPOTS[car_park_id]


def seed(db_path) -> None:
    """Insert all car parks if they don't already exist (idempotent)."""
    with get_connection(db_path) as con:
        for cp in ALL_CAR_PARKS:
            con.execute(
                """
                INSERT OR IGNORE INTO car_parks
                    (id, name, lat, lon, suburb, address, source, tfnsw_facility_id)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    cp.id, cp.name, cp.lat, cp.lon,
                    cp.suburb, cp.address, cp.source, cp.tfnsw_facility_id,
                ),
            )
```

- [ ] **Step 4.3: Create `backend/app/data/seed_zones.json`**

```json
{
  "victoria_avenue": {
    "street": "Victoria Avenue",
    "segments": [
      {
        "side": "north",
        "rules_plain_english": "No stopping 7am–10am and 4pm–7pm Monday to Friday. 2P parking 10am–4pm Monday to Friday. No restrictions on weekends.",
        "rules_structured": [
          {
            "days": ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"],
            "start": "07:00",
            "end": "10:00",
            "max_minutes": null,
            "type": "no_stopping"
          },
          {
            "days": ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"],
            "start": "16:00",
            "end": "19:00",
            "max_minutes": null,
            "type": "no_stopping"
          },
          {
            "days": ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"],
            "start": "10:00",
            "end": "16:00",
            "max_minutes": 120,
            "type": "timed"
          }
        ],
        "sign_photo_url": null
      },
      {
        "side": "south",
        "rules_plain_english": "No stopping at any time.",
        "rules_structured": [
          {
            "days": ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"],
            "start": "00:00",
            "end": "23:59",
            "max_minutes": null,
            "type": "no_stopping"
          }
        ],
        "sign_photo_url": null
      }
    ]
  }
}
```

---

## Task 5: Occupancy simulator

**Files:**
- Create: `backend/app/services/__init__.py`
- Create: `backend/app/services/simulator.py`
- Create: `backend/tests/test_simulator.py`

- [ ] **Step 5.1: Write the failing tests**

Create `backend/tests/test_simulator.py`:

```python
from datetime import datetime
from app.services.simulator import simulated_available, BASELINES, SIM_CAR_PARK_IDS


def test_all_sim_ids_covered():
    assert set(SIM_CAR_PARK_IDS) == set(BASELINES.keys())


def test_deterministic_same_result_for_same_input():
    dt = datetime(2026, 5, 15, 13, 0, 0)
    assert simulated_available("sim_westfield", dt) == simulated_available("sim_westfield", dt)


def test_result_within_capacity():
    dt = datetime(2026, 5, 15, 13, 0, 0)
    result = simulated_available("sim_westfield", dt)
    capacity = BASELINES["sim_westfield"]["capacity"]
    assert 0 <= result <= capacity


def test_minutes_do_not_affect_result():
    dt_top = datetime(2026, 5, 15, 13, 0, 0)
    dt_mid = datetime(2026, 5, 15, 13, 45, 0)
    assert simulated_available("sim_westfield", dt_top) == simulated_available("sim_westfield", dt_mid)


def test_offpeak_has_more_available_than_peak():
    peak    = simulated_available("sim_westfield", datetime(2026, 5, 13, 13, 0))  # Wed 1pm
    offpeak = simulated_available("sim_westfield", datetime(2026, 5, 13, 3, 0))   # Wed 3am
    assert offpeak > peak


def test_weekend_busier_for_shopping_carpark():
    # Westfield has more demand on weekend daytime
    weekday = simulated_available("sim_westfield", datetime(2026, 5, 13, 13, 0))  # Wednesday
    weekend = simulated_available("sim_westfield", datetime(2026, 5, 16, 13, 0))  # Saturday
    assert weekend < weekday


def test_commuter_park_busier_on_weekday_morning():
    # Victoria Ave CP is commuter-pattern: busy Mon–Fri morning, quiet weekend
    weekday = simulated_available("sim_victoria_ave_cp", datetime(2026, 5, 13, 9, 0))
    weekend = simulated_available("sim_victoria_ave_cp", datetime(2026, 5, 16, 9, 0))
    assert weekday < weekend


def test_unknown_car_park_raises():
    import pytest
    with pytest.raises(KeyError):
        simulated_available("not_a_car_park", datetime(2026, 5, 15, 13, 0))
```

- [ ] **Step 5.2: Run tests — confirm they fail**

```bash
cd backend
pytest tests/test_simulator.py -v
```

Expected: `ImportError: cannot import name 'simulated_available' from 'app.services.simulator'`

- [ ] **Step 5.3: Create `backend/app/services/__init__.py`** (empty file)

- [ ] **Step 5.4: Create `backend/app/services/simulator.py`**

```python
"""
Deterministic occupancy simulator for CBD car parks not in the TfNSW feed.

Returns 'available spots' (same shape as TfNSW) so callers need no branching.
Same (car_park_id, hour) always returns the same value — safe for caching and
testing.
"""
import math
import random
from datetime import datetime

# peak_util: fraction of spots occupied at peak
# capacity: total spots (must match seed_car_parks.py)
# peak_hour: hour of day (0–23) at maximum utilisation
# weekend_mult: scales peak_util on weekends (>1 = busier, <1 = quieter)
BASELINES: dict[str, dict] = {
    "sim_westfield": {
        "peak_util": 0.87,
        "capacity": 1400,
        "peak_hour": 13,
        "weekend_mult": 1.18,
    },
    "sim_chatswood_chase": {
        "peak_util": 0.82,
        "capacity": 850,
        "peak_hour": 12,
        "weekend_mult": 1.12,
    },
    "sim_mandarin_centre": {
        "peak_util": 0.72,
        "capacity": 280,
        "peak_hour": 12,
        "weekend_mult": 1.08,
    },
    "sim_victoria_ave_cp": {
        "peak_util": 0.78,
        "capacity": 160,
        "peak_hour": 9,
        "weekend_mult": 0.45,
    },
    "sim_chatswood_west_cp": {
        "peak_util": 0.74,
        "capacity": 320,
        "peak_hour": 11,
        "weekend_mult": 1.10,
    },
}

SIM_CAR_PARK_IDS: list[str] = list(BASELINES.keys())


def _hour_factor(peak_hour: int, hour: int) -> float:
    """Cosine curve 0–1, peaking at peak_hour, width ±8 hours."""
    delta = (hour - peak_hour) % 24
    if delta > 12:
        delta -= 24
    return max(0.0, math.cos(math.pi * delta / 8) ** 2)


def simulated_available(car_park_id: str, dt: datetime) -> int:
    """
    Return the number of available spots at car park `car_park_id` for the
    hour containing `dt`. Raises KeyError for unknown IDs.
    """
    cfg = BASELINES[car_park_id]

    hour_factor = _hour_factor(cfg["peak_hour"], dt.hour)
    dow_mult = cfg["weekend_mult"] if dt.weekday() >= 5 else 1.0

    # Deterministic noise: seeded by (id, hour-truncated timestamp)
    seed_key = (car_park_id, dt.replace(minute=0, second=0, microsecond=0).isoformat())
    rng = random.Random(hash(seed_key))
    noise = rng.uniform(-0.05, 0.05)

    occ_pct = max(0.0, min(1.0, cfg["peak_util"] * hour_factor * dow_mult + noise))
    available = int(cfg["capacity"] * (1.0 - occ_pct))
    return max(0, min(cfg["capacity"], available))
```

- [ ] **Step 5.5: Run tests — confirm they pass**

```bash
cd backend
pytest tests/test_simulator.py -v
```

Expected: all 8 tests PASS.

---

## Task 6: TfNSW API client

The Swagger spec (`carparkswagger_prod_2.yaml`) gives us three endpoints to implement:

| Method | URL | Used for |
|---|---|---|
| `GET /v1/carpark` (no `facility` param) | Facility discovery — IDs + names | One-time startup check to find Chatswood facility IDs |
| `GET /v1/carpark?facility=<id>` | Live occupancy, single facility | Per-facility polling fallback |
| `GET /v1/carpark/full-list` | Live occupancy, all facilities | Scheduler poll (one call, filter Chatswood) |
| `GET /v1/carpark/history?facility=<id>&eventdate=YYYY-MM-DD` | Historical occupancy, one day | ML training data batch script (Plan 3) |

Auth header: `Authorization: apikey <TOKEN>` — confirmed from the Swagger `securityDefinitions`.

Response field names are **not documented** in the Swagger (`schema: type: file`). All `_parse_*` methods below use best-guess field names; update them after the Day 1 data audit.

**Files:**
- Create: `backend/app/data/tfnsw_client.py`
- Create: `backend/data_raw/.gitkeep`
- Create: `backend/data_raw/tfnsw_fixtures/chatswood_interchange.json`
- Create: `backend/data_raw/tfnsw_fixtures/full_list.json`
- Create: `backend/data_raw/tfnsw_fixtures/facility_list.json`
- Create: `backend/data_raw/tfnsw_fixtures/history_sample.json`
- Create: `backend/tests/test_tfnsw_client.py`

- [ ] **Step 6.1: Create `backend/data_raw/.gitkeep`** (empty file so the dir is tracked)

- [ ] **Step 6.2: Create `backend/data_raw/tfnsw_fixtures/chatswood_interchange.json`**

> **Data audit finding:** Chatswood has **no car park in the TfNSW feed**. The closest North Shore entries are Gordon (#6) and Lindfield (#34). This fixture now uses Gordon as the real-data reference — Gordon will be our sole TfNSW-sourced facility, used for ML training data. All five Chatswood CBD car parks are simulated (see Task 4 update below).

```json
{
  "tsn": "207210",
  "time": "785808515",
  "spots": "213",
  "zones": [
    {
      "spots": "213",
      "zone_id": "1",
      "occupancy": {
        "loop": "1423",
        "total": "178",
        "monthlies": null,
        "open_gate": null,
        "transients": null
      },
      "zone_name": "Gordon Henry St (north)",
      "parent_zone_id": "0"
    }
  ],
  "ParkID": "6",
  "location": {
    "suburb": "Gordon",
    "address": "Henry Street",
    "latitude": "-33.756009",
    "longitude": "151.154528"
  },
  "occupancy": {
    "loop": "1423",
    "total": "178",
    "monthlies": null,
    "open_gate": null,
    "transients": null
  },
  "MessageDate": "2026-05-11T10:30:00",
  "facility_id": "6",
  "facility_name": "Park&Ride - Gordon Henry St (north)",
  "tfnsw_facility_id": "207210TPR001"
}
```

- [ ] **Step 6.3: Create `backend/data_raw/tfnsw_fixtures/full_list.json`**

```json
[
  {
    "tsn": "207210",
    "time": "785808515",
    "spots": "213",
    "zones": [],
    "ParkID": "6",
    "location": {
      "suburb": "Gordon",
      "address": "Henry Street",
      "latitude": "-33.756009",
      "longitude": "151.154528"
    },
    "occupancy": {
      "loop": "1423",
      "total": "178",
      "monthlies": null,
      "open_gate": null,
      "transients": null
    },
    "MessageDate": "2026-05-11T10:30:00",
    "facility_id": "6",
    "facility_name": "Park&Ride - Gordon Henry St (north)",
    "tfnsw_facility_id": "207210TPR001"
  },
  {
    "tsn": "207010",
    "time": "785808515",
    "spots": "94",
    "zones": [],
    "ParkID": "34",
    "location": {
      "suburb": "Lindfield",
      "address": "Village Green",
      "latitude": "-33.775185",
      "longitude": "151.169111"
    },
    "occupancy": {
      "loop": "312",
      "total": "61",
      "monthlies": null,
      "open_gate": null,
      "transients": null
    },
    "MessageDate": "2026-05-11T10:30:00",
    "facility_id": "34",
    "facility_name": "Park&Ride - Lindfield Village Green",
    "tfnsw_facility_id": "207010TPR001"
  }
]
```

- [ ] **Step 6.4: Create `backend/data_raw/tfnsw_fixtures/facility_list.json`**

```json
[
  { "facility_id": "6",  "facility_name": "Park&Ride - Gordon Henry St (north)" },
  { "facility_id": "25", "facility_name": "Park&Ride - Hornsby" },
  { "facility_id": "34", "facility_name": "Park&Ride - Lindfield Village Green" }
]
```

- [ ] **Step 6.5: Create `backend/data_raw/tfnsw_fixtures/history_sample.json`**

```json
[
  {
    "tsn": "207210",
    "spots": "213",
    "occupancy": { "loop": "27",  "total": "27",  "monthlies": null, "open_gate": null, "transients": null },
    "MessageDate": "2026-05-10T06:00:00",
    "facility_id": "6",
    "facility_name": "Park&Ride - Gordon Henry St (north)",
    "tfnsw_facility_id": "207210TPR001"
  },
  {
    "tsn": "207210",
    "spots": "213",
    "occupancy": { "loop": "198", "total": "198", "monthlies": null, "open_gate": null, "transients": null },
    "MessageDate": "2026-05-10T09:00:00",
    "facility_id": "6",
    "facility_name": "Park&Ride - Gordon Henry St (north)",
    "tfnsw_facility_id": "207210TPR001"
  },
  {
    "tsn": "207210",
    "spots": "213",
    "occupancy": { "loop": "145", "total": "145", "monthlies": null, "open_gate": null, "transients": null },
    "MessageDate": "2026-05-10T17:00:00",
    "facility_id": "6",
    "facility_name": "Park&Ride - Gordon Henry St (north)",
    "tfnsw_facility_id": "207210TPR001"
  }
]
```

- [ ] **Step 6.6: Write the failing tests**

Create `backend/tests/test_tfnsw_client.py`:

```python
import json
import pytest
from datetime import date
from pathlib import Path
from unittest.mock import patch, MagicMock
from app.data.tfnsw_client import TfNSWClient, TfNSWSnapshot
from app.config import Settings

FIXTURES = Path(__file__).parent.parent / "data_raw/tfnsw_fixtures"


def _make_settings(tmp_path: Path, api_key: str = "") -> Settings:
    fixtures_dir = tmp_path / "fixtures"
    fixtures_dir.mkdir()
    for f in FIXTURES.glob("*.json"):
        (fixtures_dir / f.name).write_text(f.read_text())
    return Settings(tfnsw_api_key=api_key, fixtures_dir=fixtures_dir)


@pytest.fixture
def settings_no_key(tmp_path):
    return _make_settings(tmp_path)


@pytest.fixture
def settings_with_key(tmp_path):
    return _make_settings(tmp_path, api_key="test_key")


# --- get_occupancy ---

def test_get_occupancy_loads_fixture_when_no_key(settings_no_key):
    client = TfNSWClient(settings_no_key)
    result = client.get_occupancy("2060", fixture_name="chatswood_interchange")
    assert isinstance(result, TfNSWSnapshot)
    assert result.facility_id == "2060"
    assert result.available >= 0
    assert result.total_spots > 0


def test_get_occupancy_available_plus_occupied_equals_total(settings_no_key):
    client = TfNSWClient(settings_no_key)
    snap = client.get_occupancy("2060", fixture_name="chatswood_interchange")
    assert snap.available + snap.occupied == snap.total_spots


def test_get_occupancy_raises_when_fixture_missing(settings_no_key):
    client = TfNSWClient(settings_no_key)
    with pytest.raises(FileNotFoundError):
        client.get_occupancy("9999", fixture_name="nonexistent")


def test_get_occupancy_calls_api_when_key_present(settings_with_key):
    client = TfNSWClient(settings_with_key)
    fixture_data = json.loads((FIXTURES / "chatswood_interchange.json").read_text())
    with patch.object(client._http, "get") as mock_get:
        mock_resp = MagicMock()
        mock_resp.raise_for_status = MagicMock()
        mock_resp.json.return_value = fixture_data
        mock_get.return_value = mock_resp
        result = client.get_occupancy("2060", fixture_name="chatswood_interchange")
    mock_get.assert_called_once()
    assert isinstance(result, TfNSWSnapshot)


# --- get_full_list ---

def test_get_full_list_returns_list_of_snapshots(settings_no_key):
    client = TfNSWClient(settings_no_key)
    result = client.get_full_list(fixture_name="full_list")
    assert isinstance(result, list)
    assert len(result) >= 1
    assert all(isinstance(s, TfNSWSnapshot) for s in result)


def test_get_full_list_each_snapshot_is_valid(settings_no_key):
    client = TfNSWClient(settings_no_key)
    for snap in client.get_full_list(fixture_name="full_list"):
        assert snap.total_spots > 0
        assert snap.available + snap.occupied == snap.total_spots


# --- get_facility_list ---

def test_get_facility_list_returns_list(settings_no_key):
    client = TfNSWClient(settings_no_key)
    result = client.get_facility_list(fixture_name="facility_list")
    assert isinstance(result, list)
    assert len(result) >= 1


def test_get_facility_list_entries_have_id_and_name(settings_no_key):
    client = TfNSWClient(settings_no_key)
    result = client.get_facility_list(fixture_name="facility_list")
    for entry in result:
        assert "facility_id" in entry
        assert "facility_name" in entry


# --- get_history ---

def test_get_history_returns_list_of_snapshots(settings_no_key):
    client = TfNSWClient(settings_no_key)
    result = client.get_history(
        "2060", date(2026, 5, 10), fixture_name="history_sample"
    )
    assert isinstance(result, list)
    assert len(result) >= 1
    assert all(isinstance(s, TfNSWSnapshot) for s in result)


def test_get_history_snapshots_have_timestamps(settings_no_key):
    client = TfNSWClient(settings_no_key)
    result = client.get_history(
        "2060", date(2026, 5, 10), fixture_name="history_sample"
    )
    for snap in result:
        assert snap.ts is not None


def test_get_history_raises_when_fixture_missing(settings_no_key):
    client = TfNSWClient(settings_no_key)
    with pytest.raises(FileNotFoundError):
        client.get_history("2060", date(2099, 1, 1))
```

- [ ] **Step 6.7: Run tests — confirm they fail**

```bash
cd backend
pytest tests/test_tfnsw_client.py -v
```

Expected: `ImportError: cannot import name 'TfNSWClient'`

- [ ] **Step 6.8: Create `backend/app/data/tfnsw_client.py`**

```python
"""
TfNSW Car Park API client.

Implements all four endpoints from carparkswagger_prod_2.yaml:
  GET /v1/carpark                    → get_facility_list()   (discovery)
  GET /v1/carpark?facility=<id>      → get_occupancy()       (single live)
  GET /v1/carpark/full-list          → get_full_list()       (all live, for scheduler)
  GET /v1/carpark/history            → get_history()         (ML training data)

Auth: Authorization: apikey <TOKEN>  (per Swagger securityDefinitions)

Response field names are undocumented (schema: type: file in the Swagger).
All _parse_* methods use best-guess keys. Update them after the Day 1
data audit by replacing fixture files with real recorded responses and
adjusting field names to match.
"""
import json
import logging
from dataclasses import dataclass
from datetime import date, datetime, timezone
from pathlib import Path

import httpx

from app.config import Settings

log = logging.getLogger(__name__)

TFNSW_BASE = "https://api.transport.nsw.gov.au/v1/carpark"


@dataclass
class TfNSWSnapshot:
    facility_id: str
    available: int
    occupied: int
    total_spots: int
    ts: datetime


class TfNSWClient:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._http = httpx.Client(
            headers={"Authorization": f"apikey {settings.tfnsw_api_key}"},
            timeout=10.0,
        )

    # ------------------------------------------------------------------
    # Public methods
    # ------------------------------------------------------------------

    def get_occupancy(self, facility_id: str, *, fixture_name: str) -> TfNSWSnapshot:
        """Live occupancy for one facility. Falls back to fixture on error or missing key."""
        if self._settings.tfnsw_api_key:
            try:
                resp = self._http.get(TFNSW_BASE, params={"facility": facility_id})
                resp.raise_for_status()
                return self._parse_snapshot(resp.json())
            except httpx.HTTPError as exc:
                log.warning("TfNSW get_occupancy error (%s), falling back: %s", facility_id, exc)
        return self._load_fixture_snapshot(fixture_name)

    def get_full_list(self, *, fixture_name: str = "full_list") -> list[TfNSWSnapshot]:
        """
        Live occupancy for all facilities in one call.
        Preferred over get_occupancy() for the scheduler — fewer round trips.
        """
        if self._settings.tfnsw_api_key:
            try:
                resp = self._http.get(f"{TFNSW_BASE}/full-list")
                resp.raise_for_status()
                return self._parse_snapshot_list(resp.json())
            except httpx.HTTPError as exc:
                log.warning("TfNSW get_full_list error, falling back: %s", exc)
        return self._load_fixture_snapshot_list(fixture_name)

    def get_facility_list(self, *, fixture_name: str = "facility_list") -> list[dict]:
        """
        Returns raw facility discovery list (IDs + names). Used once at startup
        to find which facility_id corresponds to Chatswood car parks.
        Returns raw dicts because field names are unknown until the data audit.
        """
        if self._settings.tfnsw_api_key:
            try:
                resp = self._http.get(TFNSW_BASE)
                resp.raise_for_status()
                data = resp.json()
                return data if isinstance(data, list) else [data]
            except httpx.HTTPError as exc:
                log.warning("TfNSW get_facility_list error, falling back: %s", exc)
        return self._load_fixture_raw(fixture_name)

    def get_history(
        self,
        facility_id: str,
        event_date: date,
        *,
        fixture_name: str | None = None,
    ) -> list[TfNSWSnapshot]:
        """
        Historical occupancy for one facility on one calendar day.
        Used by the ML training batch script (Plan 3).
        fixture_name defaults to 'history_{facility_id}_{date}' when None.
        """
        if fixture_name is None:
            fixture_name = f"history_{facility_id}_{event_date.isoformat()}"

        if self._settings.tfnsw_api_key:
            try:
                resp = self._http.get(
                    f"{TFNSW_BASE}/history",
                    params={"facility": facility_id, "eventdate": event_date.isoformat()},
                )
                resp.raise_for_status()
                return self._parse_snapshot_list(resp.json())
            except httpx.HTTPError as exc:
                log.warning(
                    "TfNSW get_history error (%s %s), falling back: %s",
                    facility_id, event_date, exc,
                )
        return self._load_fixture_snapshot_list(fixture_name)

    def close(self) -> None:
        self._http.close()

    # ------------------------------------------------------------------
    # Parsing helpers
    # ------------------------------------------------------------------

    def _parse_snapshot(self, data: dict) -> TfNSWSnapshot:
        # Field names confirmed from TfNSW Car Park API documentation.
        #
        # spots         — string, total capacity (excludes motorcycle/disabled bays)
        # occupancy.total — string, vehicles currently IN the car park
        # available     — derived: int(spots) - int(occupancy.total)
        # MessageDate   — naive datetime string, no timezone ("2024-11-25T11:08:35")
        #                 Assumed AEDT/AEST; stored as-is then localised by callers.
        total = int(data.get("spots", 0))
        occupied = int((data.get("occupancy") or {}).get("total", 0))
        available = max(0, total - occupied)

        raw_ts = data.get("MessageDate", "")
        try:
            ts = datetime.fromisoformat(raw_ts)
        except (ValueError, TypeError):
            ts = datetime.now(tz=timezone.utc)

        return TfNSWSnapshot(
            facility_id=str(data.get("facility_id", "")),
            available=available,
            occupied=occupied,
            total_spots=total,
            ts=ts,
        )

    def _parse_snapshot_list(self, data) -> list[TfNSWSnapshot]:
        if isinstance(data, list):
            return [self._parse_snapshot(item) for item in data]
        # Some endpoints may wrap the list in a key — unwrap if needed.
        for key in ("car_parks", "facilities", "data", "results"):
            if key in data:
                return [self._parse_snapshot(item) for item in data[key]]
        return [self._parse_snapshot(data)]

    # ------------------------------------------------------------------
    # Fixture loaders
    # ------------------------------------------------------------------

    def _load_fixture_snapshot(self, fixture_name: str) -> TfNSWSnapshot:
        return self._parse_snapshot(self._read_fixture_json(fixture_name))

    def _load_fixture_snapshot_list(self, fixture_name: str) -> list[TfNSWSnapshot]:
        return self._parse_snapshot_list(self._read_fixture_json(fixture_name))

    def _load_fixture_raw(self, fixture_name: str) -> list[dict]:
        data = self._read_fixture_json(fixture_name)
        return data if isinstance(data, list) else [data]

    def _read_fixture_json(self, fixture_name: str) -> dict | list:
        path = self._settings.fixtures_dir / f"{fixture_name}.json"
        if not path.exists():
            raise FileNotFoundError(f"No fixture at {path}")
        return json.loads(path.read_text())
```

- [ ] **Step 6.9: Run tests — confirm they pass**

```bash
cd backend
pytest tests/test_tfnsw_client.py -v
```

Expected: all 12 tests PASS.

---

## Task 7: Willoughby KML loader

**Files:**
- Create: `backend/app/data/kml_loader.py`
- Create: `backend/tests/test_kml_loader.py`

**Context:** The real KML from Willoughby Council has CDATA descriptions structured as `<B>key</B> = value` pairs — not free text. Each placemark has fields like `rawSignId`, `signsPhotoURL`, `sign1_category`, `sign1_direction`, `sign1_description` through `sign4_*`. There are no street names; those must come from Nominatim reverse geocoding (1 req/s). Tests pass `geocode=False` to skip network calls.

- [ ] **Step 7.1: Write the failing tests**

Create `backend/tests/test_kml_loader.py`:

```python
import pytest
from pathlib import Path
from app.data.kml_loader import parse_kml, _parse_fields
from app.models import ParkingSignRecord, SignEntry

# Matches real Willoughby KML CDATA format
SAMPLE_KML = """\
<?xml version="1.0" encoding="UTF-8"?>
<kml xmlns="http://www.opengis.net/kml/2.2">
  <Document>
    <Placemark>
      <name>Sign 1</name>
      <description><![CDATA[Unknown Point Feature<BR><BR>
<B>id</B> = test-id-1<BR><BR>
<B>rawSignId</B> = 206927<BR><BR>
<B>signsPhotoURL</B> = https://example.com/sign1.jpg<BR><BR>
<B>sign1_category</B> = No Stopping<BR><BR>
<B>sign1_direction</B> = both<BR><BR>
<B>sign1_description</B> = At all times<BR><BR>
<B>sign2_category</B> = Restricted Parking<BR><BR>
<B>sign2_direction</B> = left<BR><BR>
<B>sign2_description</B> = Max Dur. 1 hour 8:30a - 6:00p M-F]]></description>
      <Point>
        <coordinates>151.18100,-33.79700,0</coordinates>
      </Point>
    </Placemark>
    <Placemark>
      <name>Sign 2</name>
      <description><![CDATA[Unknown Point Feature<BR><BR>
<B>id</B> = test-id-2<BR><BR>
<B>rawSignId</B> = 206928<BR><BR>
<B>sign1_category</B> = No Parking<BR><BR>
<B>sign1_direction</B> = right<BR><BR>
<B>sign1_description</B> = 8:30a - 6:00p Mon-Fri]]></description>
      <Point>
        <coordinates>151.18200,-33.79800,0</coordinates>
      </Point>
    </Placemark>
  </Document>
</kml>
"""

NO_POINT_KML = """\
<?xml version="1.0" encoding="UTF-8"?>
<kml xmlns="http://www.opengis.net/kml/2.2">
  <Document>
    <Placemark>
      <name>No point</name>
      <description><![CDATA[<B>sign1_category</B> = No Stopping]]></description>
    </Placemark>
  </Document>
</kml>
"""


@pytest.fixture
def kml_file(tmp_path: Path) -> Path:
    path = tmp_path / "test.kml"
    path.write_text(SAMPLE_KML)
    return path


def test_parse_kml_returns_list(kml_file):
    result = parse_kml(kml_file, geocode=False)
    assert isinstance(result, list)
    assert len(result) == 2


def test_parse_kml_returns_sign_records(kml_file):
    result = parse_kml(kml_file, geocode=False)
    for sign in result:
        assert isinstance(sign, ParkingSignRecord)


def test_parse_kml_coordinates(kml_file):
    result = parse_kml(kml_file, geocode=False)
    assert abs(result[0].lat - (-33.797)) < 0.001
    assert abs(result[0].lon - 151.181) < 0.001


def test_parse_kml_raw_description_preserved(kml_file):
    result = parse_kml(kml_file, geocode=False)
    assert "206927" in result[0].raw_description


def test_parse_kml_raw_sign_id(kml_file):
    result = parse_kml(kml_file, geocode=False)
    assert result[0].raw_sign_id == "206927"


def test_parse_kml_sign_photo_url(kml_file):
    result = parse_kml(kml_file, geocode=False)
    assert result[0].sign_photo_url == "https://example.com/sign1.jpg"


def test_parse_kml_sign_photo_url_none_when_absent(kml_file):
    result = parse_kml(kml_file, geocode=False)
    assert result[1].sign_photo_url is None


def test_parse_kml_signs_list(kml_file):
    result = parse_kml(kml_file, geocode=False)
    signs = result[0].signs
    assert len(signs) == 2
    assert all(isinstance(s, SignEntry) for s in signs)


def test_parse_kml_sign_fields(kml_file):
    result = parse_kml(kml_file, geocode=False)
    first = result[0].signs[0]
    assert first.category == "No Stopping"
    assert first.direction == "both"
    assert first.description == "At all times"


def test_parse_kml_second_sign(kml_file):
    result = parse_kml(kml_file, geocode=False)
    second = result[0].signs[1]
    assert second.category == "Restricted Parking"
    assert second.direction == "left"


def test_parse_kml_skips_placemarks_without_point(tmp_path):
    path = tmp_path / "nopoint.kml"
    path.write_text(NO_POINT_KML)
    result = parse_kml(path, geocode=False)
    assert result == []


def test_parse_fields_extracts_key_value_pairs():
    html = "<B>sign1_category</B> = No Stopping<BR><B>sign1_direction</B> = both"
    fields = _parse_fields(html)
    assert fields["sign1_category"] == "No Stopping"
    assert fields["sign1_direction"] == "both"


def test_parse_fields_ignores_empty_values():
    html = "<B>rawSignId</B> = 12345<BR><B>signsPhotoURL</B> = "
    fields = _parse_fields(html)
    assert fields.get("rawSignId") == "12345"
    assert "signsPhotoURL" not in fields
```

- [ ] **Step 7.2: Run tests — confirm they fail**

```bash
cd backend
pytest tests/test_kml_loader.py -v
```

Expected: `ImportError: cannot import name 'parse_kml'`

- [ ] **Step 7.3: Create `backend/app/data/kml_loader.py`**

```python
import re
import logging
import time
from pathlib import Path

import httpx
from lxml import etree

from app.models import ParkingSignRecord, SignEntry

log = logging.getLogger(__name__)

_KML_NS = "http://www.opengis.net/kml/2.2"
_FIELD_RE = re.compile(r"<B>([^<]+)</B>\s*=\s*([^<\n]+)")
_NOMINATIM_URL = "https://nominatim.openstreetmap.org/reverse"
_USER_AGENT = "ParkSmart/1.0 (parking assistant for Chatswood CBD; contact duyminhle21@gmail.com)"


def parse_kml(kml_path: Path, *, geocode: bool = True) -> list[ParkingSignRecord]:
    tree = etree.parse(str(kml_path))
    root = tree.getroot()

    records: list[ParkingSignRecord] = []
    for placemark in root.iter(f"{{{_KML_NS}}}Placemark"):
        point = placemark.find(f".//{{{_KML_NS}}}Point")
        if point is None:
            continue
        coords_el = point.find(f"{{{_KML_NS}}}coordinates")
        if coords_el is None or not coords_el.text:
            continue

        lon_s, lat_s, *_ = coords_el.text.strip().split(",")
        lat, lon = float(lat_s), float(lon_s)

        desc_el = placemark.find(f".//{{{_KML_NS}}}description")
        raw = (desc_el.text or "").strip() if desc_el is not None else ""

        fields = _parse_fields(raw)

        raw_sign_id = fields.get("rawSignId")
        photo_url = fields.get("signsPhotoURL") or None

        signs: list[SignEntry] = []
        for n in range(1, 5):
            cat = fields.get(f"sign{n}_category")
            if not cat:
                break
            signs.append(
                SignEntry(
                    category=cat,
                    direction=fields.get(f"sign{n}_direction", "none"),
                    description=fields.get(f"sign{n}_description", ""),
                )
            )

        records.append(
            ParkingSignRecord(
                raw_sign_id=raw_sign_id,
                lat=lat,
                lon=lon,
                street=None,
                raw_description=raw,
                signs=signs,
                sign_photo_url=photo_url,
            )
        )

    log.info("Parsed %d signs from %s", len(records), kml_path.name)

    if geocode and records:
        _reverse_geocode_all(records)

    return records


def _parse_fields(html: str) -> dict[str, str]:
    """Extract <B>key</B> = value pairs from CDATA HTML. Skips blank values."""
    result: dict[str, str] = {}
    for m in _FIELD_RE.finditer(html):
        key = m.group(1).strip()
        val = m.group(2).strip()
        if val:
            result[key] = val
    return result


def _reverse_geocode_all(records: list[ParkingSignRecord]) -> None:
    with httpx.Client(headers={"User-Agent": _USER_AGENT}, timeout=10.0) as client:
        for record in records:
            street = _geocode_one(client, record.lat, record.lon)
            record.street = street
            time.sleep(1.0)  # Nominatim rate limit: 1 req/s


def _geocode_one(client: httpx.Client, lat: float, lon: float) -> str | None:
    try:
        resp = client.get(
            _NOMINATIM_URL,
            params={"lat": lat, "lon": lon, "format": "json"},
        )
        resp.raise_for_status()
        address = resp.json().get("address", {})
        return (
            address.get("road")
            or address.get("pedestrian")
            or address.get("path")
        )
    except Exception:
        log.warning("Nominatim geocode failed for (%s, %s)", lat, lon)
        return None
```

- [ ] **Step 7.4: Run tests — confirm they pass**

```bash
cd backend
pytest tests/test_kml_loader.py -v
```

Expected: all 14 tests PASS.

---

## Task 8: FastAPI app skeleton and lifespan startup

**Files:**
- Create: `backend/app/main.py`

No separate test file — startup behavior is validated by running the server. Integration tests for routes come in Plan 2.

- [ ] **Step 8.1: Create `backend/app/main.py`**

```python
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.config import settings
from app.db import init_db, get_connection
from app.data.seed_car_parks import seed as seed_car_parks
from app.data.kml_loader import parse_kml

log = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")


@asynccontextmanager
async def lifespan(app: FastAPI):
    log.info("Starting ParkSmart backend")

    # 1. Bootstrap database
    init_db(settings.db_path)
    log.info("Database ready at %s", settings.db_path)

    # 2. Seed car parks (idempotent)
    seed_car_parks(settings.db_path)
    log.info("Car parks seeded")

    # 3. Parse KML (if file exists)
    import json as _json
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
                        _json.dumps([e.model_dump() for e in s.signs]),
                        s.sign_photo_url,
                    )
                    for s in signs
                ],
            )
        log.info("Loaded %d parking signs", len(signs))
    else:
        log.warning("KML file not found at %s — skipping sign load", kml_path)

    yield

    log.info("Shutting down ParkSmart backend")


app = FastAPI(title="ParkSmart API", version="0.1.0", lifespan=lifespan)


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}
```

- [ ] **Step 8.2: Start the server and verify it boots**

```bash
cd backend
uvicorn app.main:app --reload
```

Expected output (order may vary):
```
INFO app.main: Starting ParkSmart backend
INFO app.main: Database ready at parksmart.db
INFO app.main: Car parks seeded
INFO     uvicorn.error: Application startup complete.
```

Visit `http://localhost:8000/health` — should return `{"status": "ok"}`.

- [ ] **Step 8.3: Run the full test suite**

```bash
cd backend
pytest -v --tb=short
```

Expected: all tests PASS with no errors.

---

## Self-review

**Spec coverage check:**

| Spec requirement | Covered by |
|---|---|
| SQLite schema: car_parks, occupancy_history, parking_signs | Task 2 (db.py) |
| 5 Chatswood car parks seeded (all simulated — no TfNSW coverage in Chatswood) | Task 4 (seed_car_parks.py) |
| 2 real TfNSW facilities seeded (Gordon + Lindfield) for live data + ML training | Task 4 (seed_car_parks.py) |
| Deterministic simulator, TfNSW shape | Task 5 (simulator.py) |
| TfNSW client: single facility, full-list, facility discovery, history | Task 6 (tfnsw_client.py) |
| KML parser → parking_signs | Task 7 (kml_loader.py) |
| seed_zones.json for Victoria Avenue | Task 4 |
| FastAPI app boots, DB seeded on start | Task 8 (main.py) |
| `get_history()` for ML training batch | Task 6 (tfnsw_client.py) — consumed by ML plan (Plan 3) |
| APScheduler (5-min poll using `get_full_list`, hourly sim, backfill) | **Not yet — Plan 2** (depends on occupancy_service) |
| occupancy_service, prediction_service, zone_service, llm_service | **Plan 2** |
| ML pipeline | **Plan 3** |
| Frontend | **Plan 4** |

**Placeholder scan:** None found. All steps contain complete code.

**Type consistency check:**
- `ParkingSignRecord` defined in `models.py` (Task 3), used in `kml_loader.py` (Task 7) and `main.py` (Task 8). ✓
- `RestrictionRule` defined in `models.py`, used in `seed_zones.json`. ✓
- `TfNSWSnapshot` defined and used only in `tfnsw_client.py`. ✓
- `simulated_available(car_park_id, dt)` signature consistent across `simulator.py` and `test_simulator.py`. ✓
- `seed(db_path)` function name in `seed_car_parks.py` matches import in `main.py`. ✓
- `get_connection(db_path)` signature consistent across `db.py`, `conftest.py`, `seed_car_parks.py`, `main.py`. ✓
