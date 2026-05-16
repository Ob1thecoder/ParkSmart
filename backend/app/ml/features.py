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
