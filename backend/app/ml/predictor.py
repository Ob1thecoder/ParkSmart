"""Inference wrapper around the trained site-agnostic occupancy model."""
import logging
import pickle
from datetime import datetime, timedelta, timezone
from functools import lru_cache
from pathlib import Path

import pandas as pd

from app.data.seed_car_parks import ALL_CAR_PARKS
from app.db import get_connection
from app.ml.features import FEATURE_COLUMNS, build_feature_row

log = logging.getLogger(__name__)


def _default_model_file() -> Path:
    here = Path(__file__).resolve()
    flat = here.parent.parent / "models" / "occupancy_v1.pkl"
    nested = here.parents[2] / "models" / "occupancy_v1.pkl"
    if flat.exists():
        return flat
    if nested.exists():
        return nested
    return flat


MODEL_PATH = _default_model_file()

_NAME_BY_ID = {cp.id: cp.name for cp in ALL_CAR_PARKS}
_CAR_PARK_BY_ID = {cp.id: cp for cp in ALL_CAR_PARKS}


@lru_cache(maxsize=8)
def load_bundle(path: Path) -> dict | None:
    """Load and cache a pickled model bundle. Returns None if the file is absent."""
    if not path.exists():
        return None
    with path.open("rb") as fh:
        return pickle.load(fh)


def _occ_frac(available: int, total: int) -> float:
    if not total:
        return 0.0
    return max(0.0, min(1.0, 1.0 - available / total))


def _utc_naive_iso(dt: datetime) -> str:
    """SQLite stores TfNSW history as naive ``MessageDate``-style timestamps."""
    if dt.tzinfo is not None:
        dt = dt.astimezone(timezone.utc).replace(tzinfo=None)
    return dt.replace(microsecond=0).isoformat(timespec="seconds")


def _ts_to_utc_unix(s: str) -> float:
    raw = datetime.fromisoformat(s.replace("Z", "+00:00"))
    if raw.tzinfo is None:
        raw = raw.replace(tzinfo=timezone.utc)
    return raw.astimezone(timezone.utc).timestamp()


def _lag_occupancy(
    db_path: Path, car_park_id: str, when: datetime, fallback: float
) -> tuple[float, bool]:
    """Occupancy fraction near ``when`` for this car park.

    Returns ``(value, imputed)`` where ``imputed`` is True when ``fallback`` was used.
    """
    when_ts = _ts_to_utc_unix(when.isoformat())

    def _nearest(rows: list) -> float:
        best_row = min(
            rows,
            key=lambda r: abs(_ts_to_utc_unix(r["ts"]) - when_ts),
        )
        return _occ_frac(best_row["available"], best_row["total_spots"])

    lo = _utc_naive_iso(when - timedelta(minutes=90))
    hi = _utc_naive_iso(when + timedelta(minutes=90))
    with get_connection(db_path) as con:
        tight = con.execute(
            "SELECT ts, available, total_spots FROM occupancy_history "
            "WHERE car_park_id = ? AND ts BETWEEN ? AND ? ",
            (car_park_id, lo, hi),
        ).fetchall()
    if tight:
        return _nearest(tight), False

    wlo = _utc_naive_iso(when - timedelta(hours=72))
    whi = _utc_naive_iso(when + timedelta(hours=72))
    with get_connection(db_path) as con:
        wide = con.execute(
            "SELECT ts, available, total_spots FROM occupancy_history "
            "WHERE car_park_id = ? AND ts BETWEEN ? AND ? ",
            (car_park_id, wlo, whi),
        ).fetchall()
    if wide:
        return _nearest(wide), False

    cap = _utc_naive_iso(when - timedelta(days=180))
    ts_bound = _utc_naive_iso(when)
    with get_connection(db_path) as con:
        row = con.execute(
            "SELECT ts, available, total_spots FROM occupancy_history "
            "WHERE car_park_id = ? AND ts BETWEEN ? AND ? "
            "ORDER BY ts DESC LIMIT 1 ",
            (car_park_id, cap, ts_bound),
        ).fetchone()
    if row and row["total_spots"]:
        return _occ_frac(row["available"], row["total_spots"]), False

    return fallback, True


def predict(
    car_park_id: str,
    target_dt: datetime,
    db_path: Path,
    path: Path | None = None,
) -> dict | None:
    """
    Predict occupancy for a seeded car park. Returns a PredictionResult-shaped dict,
    or None when no compatible bundle exists (caller should fall back).
    """
    bundle = load_bundle(path or MODEL_PATH)
    if bundle is None:
        return None

    if bundle.get("feature_columns") != FEATURE_COLUMNS:
        log.warning(
            "occupancy.pkl schema mismatch; expected site-agnostic %r columns. "
            "Run `python -m app.ml.train`.",
            FEATURE_COLUMNS,
        )
        return None

    cp = _CAR_PARK_BY_ID.get(car_park_id)
    if cp is None:
        log.warning("Unknown car_park_id %r — not in ALL_CAR_PARKS.", car_park_id)
        return None

    tm = bundle.get("type_mean_occupancy") or {}
    train_mean = float(bundle["train_mean_occupancy"])
    commuter_fb = float(tm.get("commuter", train_mean))
    retail_fb = float(tm.get("retail", train_mean))
    lag_fallback = commuter_fb if cp.venue_type == "commuter" else retail_fb

    lag_24h, im24 = _lag_occupancy(
        db_path, car_park_id, target_dt - timedelta(hours=24), lag_fallback
    )
    lag_168h, im168 = _lag_occupancy(
        db_path, car_park_id, target_dt - timedelta(hours=168), lag_fallback
    )

    feat = build_feature_row(
        target_dt,
        lag_24h,
        lag_168h,
        1.0 if im24 else 0.0,
        1.0 if im168 else 0.0,
        venue_type=cp.venue_type,
        total_spots=cp.total_spots,
    )
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
