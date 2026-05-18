import pytest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from app.config import Settings
from app.services import prediction_service


def _settings(seeded_db):
    return Settings(db_path=seeded_db, openai_api_key="")


# --- predict_availability_tool ---

def test_predict_sim_car_park_fallback_without_model(seeded_db, tmp_path, monkeypatch):
    from app.ml import predictor

    monkeypatch.setattr(predictor, "MODEL_PATH", tmp_path / "missing.pkl")

    target = (datetime.now(timezone.utc) + timedelta(hours=3)).isoformat()
    result = prediction_service.predict_availability_tool("Westfield", target, seeded_db)
    assert "error" not in result
    assert result["car_park_id"] == "sim_westfield"
    assert 0.0 <= result["predicted_occupancy_pct"] <= 1.0
    assert result["confidence"] == 0.7
    assert result["model_version"] == "simulator-v1"


def test_predict_sim_car_park_uses_ml_when_bundle_present(seeded_db, tmp_path, monkeypatch):
    import pickle
    import numpy as np
    import pandas as pd
    from xgboost import XGBRegressor
    from app.ml import predictor
    from app.ml.features import FEATURE_COLUMNS

    rng = np.random.default_rng(1)
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
            "type_mean_occupancy": {"commuter": 0.5, "retail": 0.5},
            "max_residual": 0.5, "model_version": "xgboost-v1",
            "trained_at": "2026-05-16T00:00:00+00:00", "n_train": 80, "n_val": 0,
        }, fh)
    monkeypatch.setattr(predictor, "MODEL_PATH", model_path)

    target = (datetime.now(timezone.utc) + timedelta(hours=3)).isoformat()
    result = prediction_service.predict_availability_tool("Westfield", target, seeded_db)
    assert "error" not in result
    assert result["car_park_id"] == "sim_westfield"
    assert result["model_version"] == "xgboost-v1"


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
            "type_mean_occupancy": {"commuter": 0.5, "retail": 0.5},
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


def test_predict_out_of_range_future(seeded_db):
    target = (datetime.now(timezone.utc) + timedelta(days=8)).isoformat()
    result = prediction_service.predict_availability_tool("Westfield", target, seeded_db)
    assert result["error"] == "out_of_range"


def test_predict_rounds_to_nearest_hour(seeded_db):
    # Minute 45 is floored to :00 — anchor a few days out so UTC "now" never passes target.
    base = datetime.now(timezone.utc) + timedelta(days=3)
    base = base.replace(hour=18, minute=45, second=0, microsecond=0)
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
