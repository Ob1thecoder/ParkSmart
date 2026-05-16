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
