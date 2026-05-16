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
