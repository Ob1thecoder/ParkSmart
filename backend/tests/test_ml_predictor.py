import pickle
from datetime import datetime, timedelta, timezone

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
        "type_mean_occupancy": {"commuter": 0.52, "retail": 0.48},
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


def test_predict_returns_none_when_bundle_schema_stale(seeded_db, tmp_path):
    rng = np.random.default_rng(0)
    truncated = FEATURE_COLUMNS[:-2]
    X = pd.DataFrame(rng.random((80, len(truncated))), columns=truncated)
    y = rng.random(80)
    occ = XGBRegressor(n_estimators=10, max_depth=2, random_state=0).fit(X, y)
    resid = XGBRegressor(n_estimators=10, max_depth=2, random_state=0).fit(
        X, np.abs(y - occ.predict(X))
    )
    stale = tmp_path / "stale.pkl"
    with stale.open("wb") as fh:
        pickle.dump(
            {
                "occupancy_model": occ,
                "residual_model": resid,
                "feature_columns": truncated,
                "train_mean_occupancy": 0.5,
                "type_mean_occupancy": {"commuter": 0.5, "retail": 0.5},
                "max_residual": 0.5,
                "model_version": "xgboost-v1",
                "trained_at": "2026-05-16T00:00:00+00:00",
                "n_train": 80,
                "n_val": 0,
            },
            fh,
        )
    result = predictor.predict(
        "tfnsw_gordon",
        datetime(2026, 5, 20, 14, tzinfo=timezone.utc),
        seeded_db,
        path=stale,
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


def test_predict_cold_start_retail_differs_from_commuter(seeded_db, tmp_path):
    """Regression: site-agnostic model must not collapse new TfNSW lots to one number."""
    rng = np.random.default_rng(42)
    X = pd.DataFrame(rng.random((200, len(FEATURE_COLUMNS))), columns=FEATURE_COLUMNS)
    y = (
        0.4 * X["is_commuter"].to_numpy()
        + 0.35 * X["lag_24h"].to_numpy()
        + 0.12 * (X["log_capacity"] / 8.0).clip(upper=1.0).to_numpy()
        + rng.random(200) * 0.03
    )
    occ = XGBRegressor(n_estimators=40, max_depth=3, random_state=0).fit(X, y)
    resid = XGBRegressor(n_estimators=10, max_depth=2, random_state=1).fit(
        X, np.abs(y - occ.predict(X))
    )
    path = tmp_path / "occ.pkl"
    with path.open("wb") as fh:
        pickle.dump(
            {
                "occupancy_model": occ,
                "residual_model": resid,
                "feature_columns": FEATURE_COLUMNS,
                "train_mean_occupancy": 0.5,
                "type_mean_occupancy": {"commuter": 0.22, "retail": 0.88},
                "max_residual": 1.0,
                "model_version": "xgboost-v1",
                "trained_at": "",
                "n_train": 200,
                "n_val": 0,
            },
            fh,
        )

    target = datetime(2030, 6, 15, 15, tzinfo=timezone.utc)
    west = predictor.predict("sim_westfield", target, seeded_db, path=path)
    fid8 = predictor.predict("tfnsw_facility_8", target, seeded_db, path=path)
    assert west is not None and fid8 is not None
    assert west["predicted_occupancy_pct"] != pytest.approx(
        fid8["predicted_occupancy_pct"], abs=1e-4
    )


def test_predict_observed_lag_changes_output_vs_fallback(seeded_db, tmp_path):
    """Near lag anchor rows replace cold-start type mean → different forecast."""
    from app.db import get_connection

    target = datetime(2030, 6, 15, 15, tzinfo=timezone.utc)
    lag_anchor = target - timedelta(hours=24)
    lag_iso = lag_anchor.strftime("%Y-%m-%dT%H:%M:%S")

    rng = np.random.default_rng(7)
    X = pd.DataFrame(rng.random((120, len(FEATURE_COLUMNS))), columns=FEATURE_COLUMNS)
    lag_col = X["lag_24h"].to_numpy()
    y = 0.65 * lag_col + rng.random(120) * 0.02
    occ = XGBRegressor(n_estimators=35, max_depth=3, random_state=2).fit(X, y)
    resid = XGBRegressor(n_estimators=8, max_depth=2, random_state=3).fit(
        X, np.abs(y - occ.predict(X))
    )
    bundle_common = {
        "occupancy_model": occ,
        "residual_model": resid,
        "feature_columns": FEATURE_COLUMNS,
        "train_mean_occupancy": 0.5,
        "type_mean_occupancy": {"commuter": 0.94, "retail": 0.94},
        "max_residual": 1.0,
        "model_version": "xgboost-v1",
        "trained_at": "",
        "n_train": 120,
        "n_val": 0,
    }
    path = tmp_path / "lag.pkl"
    with path.open("wb") as fh:
        pickle.dump(bundle_common, fh)

    with get_connection(seeded_db) as con:
        con.execute("DELETE FROM occupancy_history WHERE car_park_id = ?", ("tfnsw_gordon",))
        con.execute(
            "INSERT OR REPLACE INTO occupancy_history "
            "(car_park_id, ts, available, total_spots) VALUES (?, ?, ?, ?)",
            ("tfnsw_gordon", lag_iso, 200, 213),
        )

    with_hist = predictor.predict("tfnsw_gordon", target, seeded_db, path=path)

    with get_connection(seeded_db) as con:
        con.execute("DELETE FROM occupancy_history WHERE car_park_id = ?", ("tfnsw_gordon",))

    cold = predictor.predict("tfnsw_gordon", target, seeded_db, path=path)

    assert with_hist is not None and cold is not None
    assert with_hist["predicted_occupancy_pct"] != pytest.approx(
        cold["predicted_occupancy_pct"], abs=1e-3
    )
