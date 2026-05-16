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
