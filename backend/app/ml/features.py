"""Site-agnostic occupancy features for the XGBoost regressor.

Fixed **12-column** schema: temporal context + venue kind + capacity + lags (+ imputed flags).
Adding a car park does not change ``FEATURE_COLUMNS``.

Regression target (``build_training_frame``): hourly mean occupancy fraction
``1 - available/total_spots``.
"""
from __future__ import annotations

from datetime import datetime
from typing import Literal

import holidays
import numpy as np
import pandas as pd

from app.data.seed_car_parks import ALL_CAR_PARKS

_NSW_HOLIDAYS = holidays.country_holidays("AU", subdiv="NSW")

_CAR_BY_ID = {cp.id: cp for cp in ALL_CAR_PARKS}

FEATURE_COLUMNS = [
    "hour_sin",
    "hour_cos",
    "dow_sin",
    "dow_cos",
    "is_weekend",
    "is_public_holiday",
    "is_commuter",
    "log_capacity",
    "lag_24h",
    "lag_24h_imputed",
    "lag_168h",
    "lag_168h_imputed",
]


def _cyclical(value: float, period: int) -> tuple[float, float]:
    angle = 2.0 * np.pi * value / period
    return float(np.sin(angle)), float(np.cos(angle))


def build_feature_row(
    dt: datetime,
    lag_24h: float,
    lag_168h: float,
    lag_24h_imputed: float,
    lag_168h_imputed: float,
    *,
    venue_type: Literal["commuter", "retail"],
    total_spots: int,
) -> dict[str, float]:
    """Single timestep feature dict aligned with ``FEATURE_COLUMNS``."""
    hour_sin, hour_cos = _cyclical(dt.hour, 24)
    dow_sin, dow_cos = _cyclical(dt.weekday(), 7)
    cap = max(0, int(total_spots))
    return {
        "hour_sin": hour_sin,
        "hour_cos": hour_cos,
        "dow_sin": dow_sin,
        "dow_cos": dow_cos,
        "is_weekend": 1.0 if dt.weekday() >= 5 else 0.0,
        "is_public_holiday": 1.0 if dt.date() in _NSW_HOLIDAYS else 0.0,
        "is_commuter": 1.0 if venue_type == "commuter" else 0.0,
        "log_capacity": float(np.log1p(cap)),
        "lag_24h": float(lag_24h),
        "lag_24h_imputed": float(lag_24h_imputed),
        "lag_168h": float(lag_168h),
        "lag_168h_imputed": float(lag_168h_imputed),
    }


def build_training_frame(rows: list[dict]) -> pd.DataFrame:
    """
    Turn raw occupancy_history records into a model-ready frame.

    rows: dicts with keys car_park_id, ts (ISO string), available, total_spots.
    Returns columns FEATURE_COLUMNS + ['target', 'ts', 'car_park_id'],
    one row per (car park, hour). Missing lags use that car park's series mean with
    matching ``lag_*_imputed`` = 1.0.
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
        cp = _CAR_BY_ID.get(cp_id)
        if cp is None:
            continue
        occ_by_hour = dict(zip(grp["hour"], grp["occ"]))
        cp_mean = float(grp["occ"].mean())
        ts_cap = max(0, int(cp.total_spots))

        for hour, occ in occ_by_hour.items():
            raw_l24 = occ_by_hour.get(hour - pd.Timedelta(hours=24))
            if raw_l24 is None:
                lag_24h = cp_mean
                im24 = 1.0
            else:
                lag_24h = raw_l24
                im24 = 0.0

            raw_l168 = occ_by_hour.get(hour - pd.Timedelta(hours=168))
            if raw_l168 is None:
                lag_168h = cp_mean
                im168 = 1.0
            else:
                lag_168h = raw_l168
                im168 = 0.0

            feat = build_feature_row(
                hour.to_pydatetime(),
                lag_24h,
                lag_168h,
                im24,
                im168,
                venue_type=cp.venue_type,
                total_spots=ts_cap,
            )
            feat["target"] = float(occ)
            feat["ts"] = hour
            feat["car_park_id"] = cp_id
            out_rows.append(feat)

    return pd.DataFrame(out_rows, columns=columns)
