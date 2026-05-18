import logging
from datetime import datetime, timedelta, timezone
from pathlib import Path

from app.data.seed_car_parks import get_capacity
from app.ml import predictor
from app.models import PredictionResult
from app.services.occupancy_service import find_car_park
from app.services.simulator import BASELINES, simulated_available, tfnsw_ml_fallback_occupancy_fraction

log = logging.getLogger(__name__)

_MAX_FUTURE_DAYS = 7


def _simulator_prediction(car_park_id: str, name: str, target_dt: datetime) -> dict:
    """Placeholder when ML is unavailable: patterned sim for CBD garages; commuter curve for TfNSW."""
    capacity = get_capacity(car_park_id)
    if car_park_id in BASELINES:
        occupied = capacity - simulated_available(car_park_id, target_dt)
    else:
        occ_frac = tfnsw_ml_fallback_occupancy_fraction(car_park_id, target_dt)
        occupied = int(round(capacity * occ_frac))
        occupied = max(0, min(capacity, occupied))
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

    ml_result = predictor.predict(cp.id, target_dt, db_path)
    if ml_result is not None:
        return ml_result

    log.info(
        "ML predictor unavailable for %s (%s); using heuristic fallback (train & bundle ML)",
        cp.id,
        cp.name,
    )
    return _simulator_prediction(cp.id, cp.name, target_dt)
