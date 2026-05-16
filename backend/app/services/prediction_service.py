import logging
from datetime import datetime, timedelta, timezone
from pathlib import Path

from app.data.seed_car_parks import get_capacity
from app.models import PredictionResult
from app.services.occupancy_service import find_car_park
from app.services.simulator import BASELINES, simulated_available

log = logging.getLogger(__name__)

_MAX_FUTURE_DAYS = 7


def _predict_occupied(car_park_id: str, capacity: int, target_dt: datetime) -> int:
    """Return occupied count for target_dt. Uses simulator for sim parks;
    falls back to 50% occupancy for tfnsw parks until Plan 3 adds XGBoost."""
    if car_park_id in BASELINES:
        available = simulated_available(car_park_id, target_dt)
        return capacity - available
    # tfnsw parks: Plan 2 placeholder — fixed 50 % occupancy
    return capacity // 2


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

    capacity = get_capacity(cp.id)
    occupied = _predict_occupied(cp.id, capacity, target_dt)
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
