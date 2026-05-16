# ML Pipeline Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Train an XGBoost occupancy predictor on real TfNSW history for Gordon + Lindfield, expose it through a predictor module, and route TfNSW car parks to it in `prediction_service` — replacing the Plan 2 simulator placeholder.

**Architecture:** A history-collection CLI backfills the `occupancy_history` table from the TfNSW `/history` endpoint. A pure-Python feature module turns those rows into a model-ready frame. A training CLI fits two XGBoost regressors (occupancy + residual-for-confidence) and pickles a single artifact bundle. A predictor module loads the bundle and serves predictions. `prediction_service` routes `source == "tfnsw"` car parks to the predictor, falling back to the simulator when no trained model exists.

**Tech Stack:** XGBoost, pandas, numpy, holidays, SQLite (stdlib), Python 3.11+

**Depends on:** Plan 1 + Plan 2 — complete. Assumes `app.db`, `app.config`, `app.data.tfnsw_client`, `app.data.seed_car_parks`, `app.services.simulator`, `app.services.prediction_service`, and the `occupancy_history` table all exist.

---

## Audit-first, then branch

The user has a TfNSW API key but the depth of the `/history` endpoint is unverified. **Task 2 is a hard decision gate.** It runs the real collection and audits the result:

- **Gate PASS** — each TfNSW facility has **≥ 30 distinct days** and **≥ 500 hourly rows** of history. Implement Tasks 3–6 *and* run the real training in Task 4. The app ships `model_version: "xgboost-v1"`.
- **Gate FAIL** — still implement Tasks 3–6 (all code + unit tests pass with synthetic test fixtures), but **skip the real training run** in Task 4. With no `.pkl` artifact, the predictor returns `None` and `prediction_service` falls back to `simulator-v1`. Document the shortfall in `models/data_audit.md`. Re-run Task 4's training later once the Plan 2 scheduler has accumulated enough history.

Either way the plan produces working, tested software. The gate only decides whether the deployed model is real.

---

## File structure

```
backend/
├── app/
│   ├── ml/
│   │   ├── __init__.py            CREATE — empty
│   │   ├── collect_history.py     CREATE — CLI: backfill TfNSW /history into occupancy_history
│   │   ├── features.py            CREATE — occupancy_history rows → model feature frame
│   │   ├── train.py               CREATE — CLI: fit XGBoost occupancy + residual models, save bundle
│   │   └── predictor.py           CREATE — load bundle, predict(car_park_id, dt) → dict | None
│   └── services/
│       └── prediction_service.py  REWRITE — route tfnsw parks to predictor, sim parks to simulator
├── models/                        CREATE (dir) — occupancy_v1.pkl (gitignored), eval_report.md, data_audit.md
├── pyproject.toml                 MODIFY — add holidays dependency
└── tests/
    ├── test_collect_history.py    CREATE
    ├── test_ml_features.py        CREATE
    ├── test_ml_train.py           CREATE
    ├── test_ml_predictor.py       CREATE
    └── test_prediction_service.py MODIFY — tfnsw tests now exercise the XGBoost / fallback branches
```

---

## Task 1: TfNSW history collection script

**Files:**
- Create: `backend/app/ml/__init__.py`
- Create: `backend/app/ml/collect_history.py`
- Create: `backend/tests/test_collect_history.py`

**Context:** `TfNSWClient.get_history(facility_id, event_date, fixture_name=None)` returns `list[TfNSWSnapshot]` for one facility on one day. With a real `TFNSW_API_KEY` it hits the API; without a key (or on error) it loads a fixture. `occupancy_history`'s primary key is `(car_park_id, ts)` so `INSERT OR IGNORE` is idempotent. `TFNSW_CAR_PARKS` (from `app.data.seed_car_parks`) is a `list[CarPark]`; each has `.id` (e.g. `"tfnsw_gordon"`) and `.tfnsw_facility_id` (e.g. `"6"`).

- [ ] **Step 1.1: Create `backend/app/ml/__init__.py`** (empty file)

- [ ] **Step 1.2: Write the failing tests**

Create `backend/tests/test_collect_history.py`:

```python
from datetime import date
from app.config import Settings
from app.db import get_connection
from app.ml.collect_history import collect_history


def test_collect_history_inserts_rows(seeded_db):
    settings = Settings(db_path=seeded_db, tfnsw_api_key="")
    stats = collect_history(
        seeded_db, settings, days=3, today=date(2026, 5, 20), fixture_name="history_sample"
    )
    assert stats["rows_inserted"] == 6  # 3 per car park (fixed fixture timestamps)
    assert stats["by_car_park"]["tfnsw_gordon"] == 3
    assert stats["by_car_park"]["tfnsw_lindfield"] == 3


def test_collect_history_writes_tfnsw_car_park_ids(seeded_db):
    settings = Settings(db_path=seeded_db, tfnsw_api_key="")
    collect_history(
        seeded_db, settings, days=2, today=date(2026, 5, 20), fixture_name="history_sample"
    )
    with get_connection(seeded_db) as con:
        rows = con.execute(
            "SELECT DISTINCT car_park_id FROM occupancy_history "
            "WHERE car_park_id LIKE 'tfnsw_%'"
        ).fetchall()
    ids = {r["car_park_id"] for r in rows}
    assert ids == {"tfnsw_gordon", "tfnsw_lindfield"}


def test_collect_history_is_idempotent(seeded_db):
    settings = Settings(db_path=seeded_db, tfnsw_api_key="")
    kwargs = dict(days=3, today=date(2026, 5, 20), fixture_name="history_sample")
    collect_history(seeded_db, settings, **kwargs)
    stats2 = collect_history(seeded_db, settings, **kwargs)
    assert stats2["rows_inserted"] == 0  # all rows already present
```

- [ ] **Step 1.3: Run tests — confirm they fail**

Run: `cd backend && python3 -m pytest tests/test_collect_history.py -v`
Expected: `ImportError: cannot import name 'collect_history'`.

- [ ] **Step 1.4: Create `backend/app/ml/collect_history.py`**

```python
"""
TfNSW history collection — backfills real Gordon + Lindfield occupancy into the
occupancy_history table so the XGBoost model has training data.

Run:  python -m app.ml.collect_history --days 120
Requires TFNSW_API_KEY in .env to fetch real data. Without a key the underlying
client falls back to fixtures.
"""
import argparse
import logging
from datetime import date, datetime, timedelta
from pathlib import Path

from app.config import Settings, settings as _settings
from app.data.seed_car_parks import TFNSW_CAR_PARKS
from app.data.tfnsw_client import TfNSWClient
from app.db import get_connection

log = logging.getLogger(__name__)


def collect_history(
    db_path: Path,
    settings: Settings,
    days: int,
    today: date | None = None,
    fixture_name: str | None = None,
) -> dict:
    """
    Pull `days` calendar days of TfNSW history for every TfNSW car park and
    insert hourly snapshots into occupancy_history (idempotent).

    Returns {"rows_inserted": int, "by_car_park": {car_park_id: int}}.
    """
    if today is None:
        today = datetime.now().date()

    by_car_park: dict[str, int] = {}
    with TfNSWClient(settings) as client:
        with get_connection(db_path) as con:
            for cp in TFNSW_CAR_PARKS:
                inserted = 0
                for offset in range(1, days + 1):
                    event_date = today - timedelta(days=offset)
                    try:
                        snapshots = client.get_history(
                            cp.tfnsw_facility_id, event_date, fixture_name=fixture_name
                        )
                    except FileNotFoundError:
                        continue
                    except Exception as exc:  # noqa: BLE001 — log and skip a bad day
                        log.warning("history fetch failed %s %s: %s", cp.id, event_date, exc)
                        continue
                    for snap in snapshots:
                        cur = con.execute(
                            "INSERT OR IGNORE INTO occupancy_history "
                            "(car_park_id, ts, available, total_spots) VALUES (?, ?, ?, ?)",
                            (cp.id, snap.ts.isoformat(), snap.available, snap.total_spots),
                        )
                        inserted += cur.rowcount
                by_car_park[cp.id] = inserted
                log.info("Collected %d new rows for %s", inserted, cp.id)

    return {"rows_inserted": sum(by_car_park.values()), "by_car_park": by_car_park}


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    parser = argparse.ArgumentParser(description="Backfill TfNSW car park history.")
    parser.add_argument("--days", type=int, default=120, help="How many days back to fetch")
    args = parser.parse_args()

    stats = collect_history(_settings.db_path, _settings, days=args.days)
    print(f"Inserted {stats['rows_inserted']} new rows")
    for cp_id, n in stats["by_car_park"].items():
        print(f"  {cp_id}: {n}")


if __name__ == "__main__":
    main()
```

- [ ] **Step 1.5: Run tests — confirm they pass**

Run: `cd backend && python3 -m pytest tests/test_collect_history.py -v`
Expected: 3 tests PASS.

---

## Task 2: Run collection + data audit — DECISION GATE

**Files:**
- Create: `backend/models/data_audit.md` (generated — not a code file)

**Context:** This is an operational task, not a code task. It runs the real collection against the live TfNSW API and decides whether a real XGBoost model is viable. It has no automated test.

- [ ] **Step 2.1: Confirm the API key is configured**

Ensure `backend/.env` contains a real `TFNSW_API_KEY=<key>`. Run:

```bash
cd backend && python3 -c "from app.config import settings; print('key set:', bool(settings.tfnsw_api_key.strip()))"
```

Expected: `key set: True`. If `False`, stop and ask the human for the key.

- [ ] **Step 2.2: Run the collection against the live API**

```bash
cd backend && python3 -m app.ml.collect_history --days 120
```

Expected: prints `Inserted N new rows` with a per-car-park breakdown. This writes real history into `parksmart.db`.

- [ ] **Step 2.3: Audit what landed in the database**

```bash
cd backend && python3 -c "
from app.config import settings
from app.db import get_connection
with get_connection(settings.db_path) as con:
    rows = con.execute('''
        SELECT car_park_id,
               COUNT(*) AS n_rows,
               COUNT(DISTINCT date(ts)) AS n_days,
               MIN(ts) AS earliest, MAX(ts) AS latest
        FROM occupancy_history
        WHERE car_park_id IN ('tfnsw_gordon','tfnsw_lindfield')
        GROUP BY car_park_id
    ''').fetchall()
for r in rows:
    print(dict(r))
"
```

- [ ] **Step 2.4: Write `backend/models/data_audit.md`**

Create the file with the audit numbers from Step 2.3 — one row per facility (`n_rows`, `n_days`, `earliest`, `latest`) — and a one-line verdict: `GATE PASS` or `GATE FAIL`.

- [ ] **Step 2.5: Apply the decision gate**

**Gate criteria:** each of `tfnsw_gordon` and `tfnsw_lindfield` must have `n_days >= 30` AND `n_rows >= 500`.

- **PASS** → continue to Task 3. Task 4 will run real training.
- **FAIL** → continue to Task 3 anyway, but in Task 4 run only the unit test (Step 4.5) and **skip the real training run** (Step 4.6). Note the skip in `data_audit.md`. The app will serve `simulator-v1` until enough history accumulates.

Either way, proceed to Task 3.

---

## Task 3: Feature engineering

**Files:**
- Modify: `backend/pyproject.toml`
- Create: `backend/app/ml/features.py`
- Create: `backend/tests/test_ml_features.py`

**Context:** Features must be derivable both for training (from many `occupancy_history` rows) and for a single future prediction. `lag_1h` from the spec is dropped — it is not reliably available for multi-hour-ahead predictions; `lag_24h` and `lag_168h` are retrievable from history for any point in the 7-day horizon. The `penalty_density` feature is dropped per CLAUDE.md ("Do not add penalty-based ML features"). NSW public holidays come from the `holidays` package rather than a hand-maintained list.

- [ ] **Step 3.1: Add the `holidays` dependency to `backend/pyproject.toml`**

In the `dependencies` list, add `"holidays>=0.50",` after the `"lxml>=5.2",` line.

- [ ] **Step 3.2: Install the new dependency**

Run: `cd backend && pip install -e ".[dev]" -q --break-system-packages`
Expected: completes with no error.

- [ ] **Step 3.3: Write the failing tests**

Create `backend/tests/test_ml_features.py`:

```python
from datetime import datetime
import pytest
from app.ml.features import (
    FEATURE_COLUMNS,
    build_feature_row,
    build_training_frame,
)


def test_feature_row_has_all_columns():
    row = build_feature_row("tfnsw_gordon", datetime(2026, 5, 20, 14), 0.5, 0.6)
    assert set(row.keys()) == set(FEATURE_COLUMNS)


def test_feature_row_one_hot_car_park():
    gordon = build_feature_row("tfnsw_gordon", datetime(2026, 5, 20, 14), 0.5, 0.5)
    lindfield = build_feature_row("tfnsw_lindfield", datetime(2026, 5, 20, 14), 0.5, 0.5)
    assert gordon["is_gordon"] == 1.0 and gordon["is_lindfield"] == 0.0
    assert lindfield["is_lindfield"] == 1.0 and lindfield["is_gordon"] == 0.0


def test_feature_row_weekend_flag():
    saturday = build_feature_row("tfnsw_gordon", datetime(2026, 5, 23, 10), 0.5, 0.5)
    monday = build_feature_row("tfnsw_gordon", datetime(2026, 5, 25, 10), 0.5, 0.5)
    assert saturday["is_weekend"] == 1.0
    assert monday["is_weekend"] == 0.0


def test_feature_row_public_holiday_flag():
    # 2026-01-26 is Australia Day — a NSW public holiday
    holiday = build_feature_row("tfnsw_gordon", datetime(2026, 1, 26, 10), 0.5, 0.5)
    ordinary = build_feature_row("tfnsw_gordon", datetime(2026, 5, 20, 10), 0.5, 0.5)
    assert holiday["is_public_holiday"] == 1.0
    assert ordinary["is_public_holiday"] == 0.0


def test_feature_row_cyclical_bounds():
    row = build_feature_row("tfnsw_gordon", datetime(2026, 5, 20, 14), 0.5, 0.5)
    for key in ("hour_sin", "hour_cos", "dow_sin", "dow_cos"):
        assert -1.0001 <= row[key] <= 1.0001


def test_build_training_frame_empty():
    frame = build_training_frame([])
    assert list(frame.columns) == FEATURE_COLUMNS + ["target", "ts", "car_park_id"]
    assert len(frame) == 0


def test_build_training_frame_computes_target_and_lags():
    # Same hour across three days so lag_24h chains; 213-spot Gordon.
    rows = []
    for day in (18, 19, 20):
        for occupied in [50]:
            rows.append({
                "car_park_id": "tfnsw_gordon",
                "ts": f"2026-05-{day:02d}T08:00:00",
                "available": 213 - occupied,
                "total_spots": 213,
            })
    frame = build_training_frame(rows)
    assert len(frame) == 3
    # target = 1 - available/total = 50/213
    assert frame["target"].iloc[0] == pytest.approx(50 / 213, abs=1e-6)
    # the 2026-05-20 row should see 2026-05-19 as its lag_24h
    last = frame.sort_values("ts").iloc[-1]
    assert last["lag_24h"] == pytest.approx(50 / 213, abs=1e-6)
```

- [ ] **Step 3.4: Run tests — confirm they fail**

Run: `cd backend && python3 -m pytest tests/test_ml_features.py -v`
Expected: `ImportError: cannot import name ... from 'app.ml.features'`.

- [ ] **Step 3.5: Create `backend/app/ml/features.py`**

```python
"""Feature engineering for the TfNSW occupancy model.

Feature set (10 columns):
  hour_sin/hour_cos     cyclical hour-of-day
  dow_sin/dow_cos       cyclical day-of-week
  is_weekend            1.0 on Sat/Sun
  is_public_holiday     1.0 on NSW public holidays
  is_gordon/is_lindfield  one-hot car park
  lag_24h/lag_168h      occupancy fraction 24h / 168h earlier
"""
from datetime import datetime

import holidays
import numpy as np
import pandas as pd

_NSW_HOLIDAYS = holidays.country_holidays("AU", subdiv="NSW")

TFNSW_CAR_PARK_IDS = ["tfnsw_gordon", "tfnsw_lindfield"]

FEATURE_COLUMNS = [
    "hour_sin", "hour_cos",
    "dow_sin", "dow_cos",
    "is_weekend", "is_public_holiday",
    "is_gordon", "is_lindfield",
    "lag_24h", "lag_168h",
]


def _cyclical(value: float, period: int) -> tuple[float, float]:
    angle = 2.0 * np.pi * value / period
    return float(np.sin(angle)), float(np.cos(angle))


def build_feature_row(
    car_park_id: str, dt: datetime, lag_24h: float, lag_168h: float
) -> dict:
    """Build one feature dict for a single (car park, datetime)."""
    hour_sin, hour_cos = _cyclical(dt.hour, 24)
    dow_sin, dow_cos = _cyclical(dt.weekday(), 7)
    return {
        "hour_sin": hour_sin,
        "hour_cos": hour_cos,
        "dow_sin": dow_sin,
        "dow_cos": dow_cos,
        "is_weekend": 1.0 if dt.weekday() >= 5 else 0.0,
        "is_public_holiday": 1.0 if dt.date() in _NSW_HOLIDAYS else 0.0,
        "is_gordon": 1.0 if car_park_id == "tfnsw_gordon" else 0.0,
        "is_lindfield": 1.0 if car_park_id == "tfnsw_lindfield" else 0.0,
        "lag_24h": float(lag_24h),
        "lag_168h": float(lag_168h),
    }


def build_training_frame(rows: list[dict]) -> pd.DataFrame:
    """
    Turn raw occupancy_history records into a model-ready frame.

    rows: dicts with keys car_park_id, ts (ISO string), available, total_spots.
    Returns a DataFrame with FEATURE_COLUMNS + ['target', 'ts', 'car_park_id'],
    one row per (car park, hour). Missing lags fall back to the car park mean.
    """
    columns = FEATURE_COLUMNS + ["target", "ts", "car_park_id"]
    if not rows:
        return pd.DataFrame(columns=columns)

    df = pd.DataFrame(rows)
    df["ts"] = pd.to_datetime(df["ts"])
    df["hour"] = df["ts"].dt.floor("h")
    df["occ"] = 1.0 - df["available"] / df["total_spots"]

    hourly = (
        df.groupby(["car_park_id", "hour"], as_index=False)["occ"]
        .mean()
        .sort_values(["car_park_id", "hour"])
    )

    out_rows = []
    for cp_id, grp in hourly.groupby("car_park_id"):
        occ_by_hour = dict(zip(grp["hour"], grp["occ"]))
        cp_mean = float(grp["occ"].mean())
        for hour, occ in occ_by_hour.items():
            lag_24h = occ_by_hour.get(hour - pd.Timedelta(hours=24), cp_mean)
            lag_168h = occ_by_hour.get(hour - pd.Timedelta(hours=168), cp_mean)
            feat = build_feature_row(cp_id, hour.to_pydatetime(), lag_24h, lag_168h)
            feat["target"] = float(occ)
            feat["ts"] = hour
            feat["car_park_id"] = cp_id
            out_rows.append(feat)

    return pd.DataFrame(out_rows, columns=columns)
```

- [ ] **Step 3.6: Run tests — confirm they pass**

Run: `cd backend && python3 -m pytest tests/test_ml_features.py -v`
Expected: 7 tests PASS.

---

## Task 4: Training script

**Files:**
- Create: `backend/app/ml/train.py`
- Create: `backend/tests/test_ml_train.py`

**Context:** `train()` reads TfNSW history from `occupancy_history`, builds the feature frame, holds out the most recent 7 days for validation, fits an occupancy `XGBRegressor`, fits a second `XGBRegressor` on absolute training residuals (for confidence), and pickles a single bundle dict to `models/occupancy_v1.pkl`. It raises `RuntimeError` if there are too few rows. The unit test exercises only the insufficient-data guard; the real training run is operational and gated by Task 2.

- [ ] **Step 4.1: Write the failing test**

Create `backend/tests/test_ml_train.py`:

```python
import pytest
from app.ml.train import train


def test_train_raises_on_insufficient_data(seeded_db, tmp_path):
    # seeded_db has car parks but no occupancy_history rows.
    with pytest.raises(RuntimeError, match="training rows"):
        train(seeded_db, tmp_path / "occupancy_v1.pkl", tmp_path / "eval_report.md")
```

- [ ] **Step 4.2: Run test — confirm it fails**

Run: `cd backend && python3 -m pytest tests/test_ml_train.py -v`
Expected: `ImportError: cannot import name 'train'`.

- [ ] **Step 4.3: Create `backend/app/ml/train.py`**

```python
"""Train the TfNSW occupancy model + residual confidence model.

Run:  python -m app.ml.train
Reads real history from occupancy_history, fits two XGBoost regressors, and
writes models/occupancy_v1.pkl + models/eval_report.md.
"""
import argparse
import logging
import pickle
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd
from xgboost import XGBRegressor

from app.config import settings as _settings
from app.db import get_connection
from app.ml.features import FEATURE_COLUMNS, TFNSW_CAR_PARK_IDS, build_training_frame

log = logging.getLogger(__name__)

MODEL_VERSION = "xgboost-v1"
_MIN_TRAINING_ROWS = 200

_XGB_PARAMS = dict(
    n_estimators=200,
    max_depth=4,
    learning_rate=0.05,
    subsample=0.8,
    colsample_bytree=0.8,
    random_state=42,
)


def _load_history(db_path: Path) -> list[dict]:
    placeholders = ",".join("?" for _ in TFNSW_CAR_PARK_IDS)
    with get_connection(db_path) as con:
        rows = con.execute(
            f"SELECT car_park_id, ts, available, total_spots FROM occupancy_history "
            f"WHERE car_park_id IN ({placeholders})",
            TFNSW_CAR_PARK_IDS,
        ).fetchall()
    return [dict(r) for r in rows]


def train(
    db_path: Path, model_out: Path, report_out: Path, holdout_days: int = 7
) -> dict:
    """Fit the occupancy + residual models and persist the bundle. Returns metrics."""
    frame = build_training_frame(_load_history(db_path))
    if len(frame) < _MIN_TRAINING_ROWS:
        raise RuntimeError(
            f"Only {len(frame)} training rows (need >= {_MIN_TRAINING_ROWS}). "
            "Collect more TfNSW history before training."
        )

    cutoff = frame["ts"].max() - pd.Timedelta(days=holdout_days)
    train_df = frame[frame["ts"] <= cutoff]
    val_df = frame[frame["ts"] > cutoff]
    if len(train_df) < _MIN_TRAINING_ROWS:
        raise RuntimeError(
            f"Only {len(train_df)} rows left after the {holdout_days}-day holdout "
            f"(need >= {_MIN_TRAINING_ROWS})."
        )

    X_train = train_df[FEATURE_COLUMNS]
    y_train = train_df["target"].to_numpy()

    occ_model = XGBRegressor(**_XGB_PARAMS)
    occ_model.fit(X_train, y_train)

    abs_resid = np.abs(y_train - occ_model.predict(X_train))
    resid_model = XGBRegressor(**_XGB_PARAMS)
    resid_model.fit(X_train, abs_resid)
    max_residual = float(abs_resid.max()) if len(abs_resid) else 1.0

    if len(val_df):
        val_pred = occ_model.predict(val_df[FEATURE_COLUMNS])
        val_mae = float(np.abs(val_df["target"].to_numpy() - val_pred).mean())
    else:
        val_mae = float("nan")

    bundle = {
        "occupancy_model": occ_model,
        "residual_model": resid_model,
        "feature_columns": FEATURE_COLUMNS,
        "train_mean_occupancy": float(y_train.mean()),
        "max_residual": max_residual,
        "model_version": MODEL_VERSION,
        "trained_at": datetime.now(timezone.utc).isoformat(),
        "n_train": int(len(train_df)),
        "n_val": int(len(val_df)),
    }

    model_out.parent.mkdir(parents=True, exist_ok=True)
    with model_out.open("wb") as fh:
        pickle.dump(bundle, fh)

    report_out.parent.mkdir(parents=True, exist_ok=True)
    report_out.write_text(
        "# Occupancy Model Evaluation\n\n"
        f"- Model version: {MODEL_VERSION}\n"
        f"- Trained at: {bundle['trained_at']}\n"
        f"- Training rows: {bundle['n_train']}\n"
        f"- Validation rows: {bundle['n_val']}\n"
        f"- Validation MAE (occupancy fraction): {val_mae:.4f}\n"
        f"- Max training residual: {max_residual:.4f}\n"
    )
    log.info("Saved model to %s (validation MAE %.4f)", model_out, val_mae)
    return {"val_mae": val_mae, "n_train": bundle["n_train"], "n_val": bundle["n_val"]}


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    parser = argparse.ArgumentParser(description="Train the TfNSW occupancy model.")
    parser.add_argument("--holdout-days", type=int, default=7)
    args = parser.parse_args()

    base = Path(__file__).parent.parent.parent / "models"
    result = train(
        _settings.db_path,
        base / "occupancy_v1.pkl",
        base / "eval_report.md",
        holdout_days=args.holdout_days,
    )
    print(f"Validation MAE: {result['val_mae']:.4f}  "
          f"(train={result['n_train']}, val={result['n_val']})")


if __name__ == "__main__":
    main()
```

- [ ] **Step 4.4: Run test — confirm it passes**

Run: `cd backend && python3 -m pytest tests/test_ml_train.py -v`
Expected: 1 test PASS.

- [ ] **Step 4.5: Run real training — ONLY IF Task 2 gate PASSED**

If the Task 2 gate **passed**:

```bash
cd backend && python3 -m app.ml.train
```

Expected: prints `Validation MAE: 0.xxxx`, and creates `backend/models/occupancy_v1.pkl` + `backend/models/eval_report.md`.

If the Task 2 gate **failed**: skip this step. Add a line to `models/data_audit.md`: `Real training skipped — insufficient history. prediction_service serves simulator-v1.`

---

## Task 5: Predictor module

**Files:**
- Create: `backend/app/ml/predictor.py`
- Create: `backend/tests/test_ml_predictor.py`

**Context:** `predict()` loads the pickled bundle (cached), reads `lag_24h` / `lag_168h` from `occupancy_history` for the relevant earlier hours (falling back to the bundle's training mean when no row is near), runs both models, and returns a prediction dict. If no model artifact exists it returns `None` so the caller can fall back. The test builds a tiny bundle in `tmp_path` — this is test scaffolding, not the production training set.

- [ ] **Step 5.1: Write the failing tests**

Create `backend/tests/test_ml_predictor.py`:

```python
import pickle
from datetime import datetime, timezone

import numpy as np
import pandas as pd
import pytest
from xgboost import XGBRegressor

from app.ml import predictor
from app.ml.features import FEATURE_COLUMNS


def _tiny_bundle(path):
    rng = np.random.default_rng(0)
    X = pd.DataFrame(rng.random((80, len(FEATURE_COLUMNS))), columns=FEATURE_COLUMNS)
    y = rng.random(80)
    occ = XGBRegressor(n_estimators=10, max_depth=2, random_state=0).fit(X, y)
    resid = XGBRegressor(n_estimators=10, max_depth=2, random_state=0).fit(
        X, np.abs(y - occ.predict(X))
    )
    bundle = {
        "occupancy_model": occ,
        "residual_model": resid,
        "feature_columns": FEATURE_COLUMNS,
        "train_mean_occupancy": 0.5,
        "max_residual": 0.5,
        "model_version": "xgboost-v1",
        "trained_at": "2026-05-16T00:00:00+00:00",
        "n_train": 80,
        "n_val": 0,
    }
    with path.open("wb") as fh:
        pickle.dump(bundle, fh)
    return path


def test_predict_returns_none_without_model(seeded_db, tmp_path):
    missing = tmp_path / "no_model.pkl"
    result = predictor.predict(
        "tfnsw_gordon", datetime(2026, 5, 20, 14, tzinfo=timezone.utc), seeded_db, path=missing
    )
    assert result is None


def test_predict_returns_contract_dict(seeded_db, tmp_path):
    model_path = _tiny_bundle(tmp_path / "occupancy_v1.pkl")
    result = predictor.predict(
        "tfnsw_gordon", datetime(2026, 5, 20, 14, tzinfo=timezone.utc), seeded_db, path=model_path
    )
    assert result is not None
    assert result["car_park_id"] == "tfnsw_gordon"
    assert result["model_version"] == "xgboost-v1"
    assert 0.0 <= result["predicted_occupancy_pct"] <= 1.0
    assert 0.0 <= result["confidence"] <= 1.0
    assert "target_datetime" in result


def test_predict_name_resolved(seeded_db, tmp_path):
    model_path = _tiny_bundle(tmp_path / "occupancy_v1.pkl")
    result = predictor.predict(
        "tfnsw_gordon", datetime(2026, 5, 20, 14, tzinfo=timezone.utc), seeded_db, path=model_path
    )
    assert result["name"] == "Park&Ride - Gordon"
```

- [ ] **Step 5.2: Run tests — confirm they fail**

Run: `cd backend && python3 -m pytest tests/test_ml_predictor.py -v`
Expected: `ModuleNotFoundError: No module named 'app.ml.predictor'`.

- [ ] **Step 5.3: Create `backend/app/ml/predictor.py`**

```python
"""Inference wrapper around the trained occupancy model."""
import logging
import pickle
from datetime import datetime, timedelta
from functools import lru_cache
from pathlib import Path

import pandas as pd

from app.data.seed_car_parks import ALL_CAR_PARKS
from app.db import get_connection
from app.ml.features import build_feature_row

log = logging.getLogger(__name__)

MODEL_PATH = Path(__file__).parent.parent.parent / "models" / "occupancy_v1.pkl"

_NAME_BY_ID = {cp.id: cp.name for cp in ALL_CAR_PARKS}


@lru_cache(maxsize=8)
def load_bundle(path: Path) -> dict | None:
    """Load and cache a pickled model bundle. Returns None if the file is absent."""
    if not path.exists():
        return None
    with path.open("rb") as fh:
        return pickle.load(fh)


def _lag_occupancy(
    db_path: Path, car_park_id: str, when: datetime, fallback: float
) -> float:
    """Occupancy fraction for the row nearest `when` (within ±90 min), else `fallback`."""
    lo = (when - timedelta(minutes=90)).isoformat()
    hi = (when + timedelta(minutes=90)).isoformat()
    with get_connection(db_path) as con:
        row = con.execute(
            "SELECT available, total_spots FROM occupancy_history "
            "WHERE car_park_id = ? AND ts BETWEEN ? AND ? "
            "ORDER BY ABS(julianday(ts) - julianday(?)) LIMIT 1",
            (car_park_id, lo, hi, when.isoformat()),
        ).fetchone()
    if row and row["total_spots"]:
        return 1.0 - row["available"] / row["total_spots"]
    return fallback


def predict(
    car_park_id: str,
    target_dt: datetime,
    db_path: Path,
    path: Path | None = None,
) -> dict | None:
    """
    Predict occupancy for a TfNSW car park. Returns a PredictionResult-shaped dict,
    or None when no trained model is available (caller should fall back).
    """
    bundle = load_bundle(path or MODEL_PATH)
    if bundle is None:
        return None

    mean = bundle["train_mean_occupancy"]
    lag_24h = _lag_occupancy(db_path, car_park_id, target_dt - timedelta(hours=24), mean)
    lag_168h = _lag_occupancy(db_path, car_park_id, target_dt - timedelta(hours=168), mean)

    feat = build_feature_row(car_park_id, target_dt, lag_24h, lag_168h)
    X = pd.DataFrame([feat])[bundle["feature_columns"]]

    occ = float(bundle["occupancy_model"].predict(X)[0])
    occ = max(0.0, min(1.0, occ))

    resid = float(bundle["residual_model"].predict(X)[0])
    max_resid = bundle["max_residual"] or 1.0
    confidence = 1.0 - min(max(resid / max_resid, 0.0), 1.0)

    return {
        "car_park_id": car_park_id,
        "name": _NAME_BY_ID.get(car_park_id, car_park_id),
        "predicted_occupancy_pct": round(occ, 4),
        "confidence": round(confidence, 4),
        "target_datetime": target_dt.isoformat(),
        "model_version": bundle["model_version"],
    }
```

- [ ] **Step 5.4: Run tests — confirm they pass**

Run: `cd backend && python3 -m pytest tests/test_ml_predictor.py -v`
Expected: 3 tests PASS.

---

## Task 6: Route TfNSW car parks through the predictor

**Files:**
- Rewrite: `backend/app/services/prediction_service.py`
- Modify: `backend/tests/test_prediction_service.py`

**Context:** Plan 2's `prediction_service` returns `model_version: "simulator-v1"` for every car park. Plan 3 routes `source == "tfnsw"` car parks through `predictor.predict()`. When the predictor returns `None` (no `.pkl`), the service falls back to the simulator placeholder, so the app keeps working whether or not Task 4's real training ran. The datetime parsing / validation / hour-rounding logic is unchanged.

- [ ] **Step 6.1: Rewrite `backend/app/services/prediction_service.py`**

Replace the entire file with:

```python
import logging
from datetime import datetime, timedelta, timezone
from pathlib import Path

from app.data.seed_car_parks import get_capacity
from app.ml import predictor
from app.models import PredictionResult
from app.services.occupancy_service import find_car_park
from app.services.simulator import BASELINES, simulated_available

log = logging.getLogger(__name__)

_MAX_FUTURE_DAYS = 7


def _simulator_prediction(car_park_id: str, name: str, target_dt: datetime) -> dict:
    """Placeholder prediction: simulator for sim parks, 50% for tfnsw parks."""
    capacity = get_capacity(car_park_id)
    if car_park_id in BASELINES:
        occupied = capacity - simulated_available(car_park_id, target_dt)
    else:
        occupied = capacity // 2  # tfnsw fallback when no trained model exists
    predicted_pct = round(occupied / capacity, 4) if capacity > 0 else 0.0

    result = PredictionResult(
        car_park_id=car_park_id,
        name=name,
        predicted_occupancy_pct=predicted_pct,
        confidence=0.7,
        target_datetime=target_dt,
        model_version="simulator-v1",
    )
    return {**result.model_dump(), "target_datetime": target_dt.isoformat()}


def predict_availability_tool(
    location: str, target_datetime: str, db_path: Path
) -> dict:
    """LLM tool 2: predict_availability. Returns PredictionResult dict or error dict."""
    try:
        target_dt = datetime.fromisoformat(target_datetime)
    except (ValueError, TypeError):
        return {"error": "invalid_datetime", "detail": f"Cannot parse '{target_datetime}' as ISO8601"}

    if target_dt.tzinfo is None:
        target_dt = target_dt.replace(tzinfo=timezone.utc)

    now = datetime.now(timezone.utc)
    if target_dt < now:
        return {"error": "out_of_range", "detail": "target_datetime must be in the future"}
    if target_dt > now + timedelta(days=_MAX_FUTURE_DAYS):
        return {
            "error": "out_of_range",
            "detail": f"target_datetime must be within {_MAX_FUTURE_DAYS} days of now",
        }

    target_dt = target_dt.replace(minute=0, second=0, microsecond=0)

    cp, candidates = find_car_park(location)
    if cp is None:
        return {"error": "no_match", "candidates": candidates}

    # TfNSW car parks: use the XGBoost predictor when a trained model exists.
    if cp.source == "tfnsw":
        ml_result = predictor.predict(cp.id, target_dt, db_path)
        if ml_result is not None:
            return ml_result

    return _simulator_prediction(cp.id, cp.name, target_dt)
```

- [ ] **Step 6.2: Replace the TfNSW test in `backend/tests/test_prediction_service.py`**

Find `test_predict_tfnsw_car_park` and replace that single function with the two functions below. Leave every other test in the file unchanged.

```python
def test_predict_tfnsw_uses_xgboost_when_model_present(seeded_db, tmp_path, monkeypatch):
    import pickle
    import numpy as np
    import pandas as pd
    from xgboost import XGBRegressor
    from app.ml import predictor
    from app.ml.features import FEATURE_COLUMNS

    rng = np.random.default_rng(0)
    X = pd.DataFrame(rng.random((80, len(FEATURE_COLUMNS))), columns=FEATURE_COLUMNS)
    y = rng.random(80)
    occ = XGBRegressor(n_estimators=10, max_depth=2, random_state=0).fit(X, y)
    resid = XGBRegressor(n_estimators=10, max_depth=2, random_state=0).fit(
        X, np.abs(y - occ.predict(X))
    )
    model_path = tmp_path / "occupancy_v1.pkl"
    with model_path.open("wb") as fh:
        pickle.dump({
            "occupancy_model": occ, "residual_model": resid,
            "feature_columns": FEATURE_COLUMNS, "train_mean_occupancy": 0.5,
            "max_residual": 0.5, "model_version": "xgboost-v1",
            "trained_at": "2026-05-16T00:00:00+00:00", "n_train": 80, "n_val": 0,
        }, fh)
    monkeypatch.setattr(predictor, "MODEL_PATH", model_path)

    target = (datetime.now(timezone.utc) + timedelta(hours=3)).isoformat()
    result = prediction_service.predict_availability_tool("Gordon", target, seeded_db)
    assert "error" not in result
    assert result["car_park_id"] == "tfnsw_gordon"
    assert result["model_version"] == "xgboost-v1"


def test_predict_tfnsw_falls_back_to_simulator_without_model(seeded_db, tmp_path, monkeypatch):
    from app.ml import predictor

    monkeypatch.setattr(predictor, "MODEL_PATH", tmp_path / "missing.pkl")

    target = (datetime.now(timezone.utc) + timedelta(hours=3)).isoformat()
    result = prediction_service.predict_availability_tool("Gordon", target, seeded_db)
    assert "error" not in result
    assert result["car_park_id"] == "tfnsw_gordon"
    assert result["model_version"] == "simulator-v1"
```

- [ ] **Step 6.3: Run the prediction service tests**

Run: `cd backend && python3 -m pytest tests/test_prediction_service.py -v`
Expected: all tests PASS (the two new TfNSW tests plus the unchanged sim/error tests).

- [ ] **Step 6.4: Run the full test suite**

Run: `cd backend && python3 -m pytest -v --tb=short`
Expected: every test passes — Plan 1 (39) + Plan 2 (39) + Plan 3 (test_collect_history 3, test_ml_features 7, test_ml_train 1, test_ml_predictor 3) with the prediction-service count adjusted by +1 for the split TfNSW test.

- [ ] **Step 6.5: Confirm model artifacts are gitignored**

Run: `cd .. && git check-ignore backend/models/occupancy_v1.pkl`
Expected: prints the path (`.gitignore` already lists `backend/models/*.pkl`). The `.md` reports under `models/` remain trackable.

---

## Self-Review

### Spec coverage (design spec §8)

| Spec requirement | Covered by |
|---|---|
| Target `occupancy_pct = 1 - available/total_spots` | Task 3 `build_training_frame` |
| Cyclical hour / day-of-week encoding | Task 3 `build_feature_row` |
| `is_weekend`, `is_public_holiday` features | Task 3 (`holidays` package) |
| `car_park_id` one-hot | Task 3 `is_gordon` / `is_lindfield` |
| Lag features | Task 3 `lag_24h`, `lag_168h` (`lag_1h` dropped — see Deviations) |
| Pull TfNSW history | Task 1 `collect_history` |
| Last 7 days as validation holdout | Task 4 `train(holdout_days=7)` |
| XGBoost occupancy regressor | Task 4 `occ_model` |
| Residual model for confidence | Task 4 `resid_model`, `confidence = 1 - clip(resid/max_resid)` |
| Save model artifact | Task 4 `models/occupancy_v1.pkl` |
| `models/eval_report.md` with validation MAE | Task 4 `report_out` |
| `prediction_service` routes by source | Task 6 `cp.source == "tfnsw"` branch |
| `model_version` = `"xgboost-v1"` / `"simulator-v1"` | Tasks 4–6 |
| `penalty_density` feature | **Dropped** — CLAUDE.md forbids penalty-based ML features |

### Deviations from the spec (intentional)

- **`lag_1h` dropped.** Not reliably available for multi-hour-ahead predictions across the 7-day horizon. `lag_24h` / `lag_168h` are retrievable from `occupancy_history` for any prediction. Lower inference complexity, no accuracy loss for the horizon that matters.
- **Single artifact bundle** instead of separate `occupancy_v1.pkl` / `residual_v1.pkl` / `feature_pipeline.pkl`. One pickled dict holds both models, the feature column order, and the lag-fallback mean — eliminates version-skew between files. Feature engineering is deterministic, so no fitted pipeline object is needed (YAGNI).
- **`holidays` package** instead of a hand-maintained NSW holiday list — correct and self-updating.

### Placeholder scan

No placeholders. Every code step contains complete, runnable code. Task 2 is operational by design (live API + human decision) and is explicitly marked as having no automated test.

### Type consistency

- `collect_history(db_path, settings, days, today=None, fixture_name=None) -> dict` — Task 1; called with matching kwargs in Task 1 tests.
- `FEATURE_COLUMNS`, `TFNSW_CAR_PARK_IDS`, `build_feature_row`, `build_training_frame` — defined in Task 3, imported unchanged by Tasks 4–5 and the Task 5 / Task 6 tests.
- `train(db_path, model_out, report_out, holdout_days=7) -> dict` — Task 4; called with matching args by `main()` and the Task 4 test.
- Bundle dict keys (`occupancy_model`, `residual_model`, `feature_columns`, `train_mean_occupancy`, `max_residual`, `model_version`, `trained_at`, `n_train`, `n_val`) — written in Task 4, read in Task 5 `predict`, and reproduced exactly by the Task 5 / Task 6 test scaffolding.
- `predictor.predict(car_park_id, target_dt, db_path, path=None) -> dict | None` — Task 5; called by `prediction_service` (Task 6) without `path`, and by tests with an explicit `path` / via `monkeypatch` of `predictor.MODEL_PATH`.
- `predictor.MODEL_PATH` — module-level `Path`, monkeypatched in Task 6 tests.
- `predict_availability_tool(location, target_datetime, db_path) -> dict` — signature unchanged from Plan 2, so routers and `llm_service` need no edits.
