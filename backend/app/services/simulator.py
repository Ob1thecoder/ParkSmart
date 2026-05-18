"""
Deterministic occupancy simulator for CBD car parks not in the TfNSW feed.

Returns 'available spots' (same shape as TfNSW) so callers need no branching.
Same (car_park_id, hour) always returns the same value — safe for caching and
testing.
"""
import hashlib
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
    "sim_artarmon_hampden": {
        "peak_util": 0.71,
        "capacity": 210,
        "peak_hour": 9,
        "weekend_mult": 0.55,
    },
    "sim_st_leonards_plaza": {
        "peak_util": 0.81,
        "capacity": 340,
        "peak_hour": 8,
        "weekend_mult": 0.35,
    },
    "sim_roseville_royal_st": {
        "peak_util": 0.68,
        "capacity": 140,
        "peak_hour": 10,
        "weekend_mult": 0.40,
    },
}

SIM_CAR_PARK_IDS: list[str] = list(BASELINES.keys())


def tfnsw_ml_fallback_occupancy_fraction(car_park_id: str, dt: datetime) -> float:
    """Occupied fraction when no ML bundle is available.

    TfNSW Park&Ride sites are not in ``BASELINES``; without this they would all use
    ``capacity // 2`` (~50%). Uses a commuter-shaped hourly curve plus deterministic
    per-site noise so forecasts differ by facility and time until a trained model loads.
    """
    peak_hour = 8
    peak_util = 0.68
    weekend_mult = 0.45
    hour_factor = _hour_factor(peak_hour, dt.hour)
    dow_mult = weekend_mult if dt.weekday() >= 5 else 1.0
    seed_str = (
        f"tfnsw-fallback:{car_park_id}:"
        f"{dt.replace(minute=0, second=0, microsecond=0).isoformat()}"
    )
    seed_int = int(hashlib.md5(seed_str.encode()).hexdigest(), 16)
    rng = random.Random(seed_int)
    noise = rng.uniform(-0.06, 0.06)
    return float(max(0.03, min(0.97, peak_util * hour_factor * dow_mult + noise)))


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
    # Use MD5 for stable hash across processes (Python's hash() is randomized)
    seed_str = f"{car_park_id}:{dt.replace(minute=0, second=0, microsecond=0).isoformat()}"
    seed_int = int(hashlib.md5(seed_str.encode()).hexdigest(), 16)
    rng = random.Random(seed_int)
    noise = rng.uniform(-0.05, 0.05)

    occ_pct = max(0.0, min(1.0, cfg["peak_util"] * hour_factor * dow_mult + noise))
    available = int(cfg["capacity"] * (1.0 - occ_pct))
    return max(0, min(cfg["capacity"], available))
