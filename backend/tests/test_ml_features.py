from datetime import datetime

import pytest

from app.ml.features import FEATURE_COLUMNS, build_feature_row, build_training_frame

_EXPECTED_TWELVE = [
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


def test_feature_columns_fixed_twelve_no_park_prefix():
    assert FEATURE_COLUMNS == _EXPECTED_TWELVE
    assert len(FEATURE_COLUMNS) == 12
    assert not any(c.startswith("park__") for c in FEATURE_COLUMNS)


def test_feature_row_has_all_columns_and_venue_capacity():
    row = build_feature_row(
        datetime(2026, 5, 20, 14),
        0.5,
        0.6,
        0.0,
        1.0,
        venue_type="commuter",
        total_spots=213,
    )
    assert set(row.keys()) == set(FEATURE_COLUMNS)
    assert row["is_commuter"] == 1.0
    assert row["lag_24h_imputed"] == 0.0
    assert row["lag_168h_imputed"] == 1.0


def test_feature_row_retail_vs_commuter():
    r = build_feature_row(
        datetime(2026, 5, 20, 14), 0.4, 0.4, 0.0, 0.0,
        venue_type="retail",
        total_spots=1400,
    )
    c = build_feature_row(
        datetime(2026, 5, 20, 14), 0.4, 0.4, 0.0, 0.0,
        venue_type="commuter",
        total_spots=213,
    )
    assert r["is_commuter"] == 0.0 and c["is_commuter"] == 1.0
    assert r["log_capacity"] != pytest.approx(c["log_capacity"])


def test_feature_row_weekend_flag():
    saturday = build_feature_row(
        datetime(2026, 5, 23, 10), 0.5, 0.5, 0.0, 0.0,
        venue_type="commuter",
        total_spots=100,
    )
    monday = build_feature_row(
        datetime(2026, 5, 25, 10), 0.5, 0.5, 0.0, 0.0,
        venue_type="commuter",
        total_spots=100,
    )
    assert saturday["is_weekend"] == 1.0
    assert monday["is_weekend"] == 0.0


def test_feature_row_public_holiday_flag():
    holiday = build_feature_row(
        datetime(2026, 1, 26, 10), 0.5, 0.5, 0.0, 0.0,
        venue_type="commuter",
        total_spots=100,
    )
    ordinary = build_feature_row(
        datetime(2026, 5, 20, 10), 0.5, 0.5, 0.0, 0.0,
        venue_type="commuter",
        total_spots=100,
    )
    assert holiday["is_public_holiday"] == 1.0
    assert ordinary["is_public_holiday"] == 0.0


def test_feature_row_cyclical_bounds():
    row = build_feature_row(
        datetime(2026, 5, 20, 14), 0.5, 0.5, 0.0, 0.0,
        venue_type="commuter",
        total_spots=100,
    )
    for key in ("hour_sin", "hour_cos", "dow_sin", "dow_cos"):
        assert -1.0001 <= row[key] <= 1.0001


def test_build_training_frame_empty():
    frame = build_training_frame([])
    assert list(frame.columns) == FEATURE_COLUMNS + ["target", "ts", "car_park_id"]
    assert len(frame) == 0


def test_build_training_frame_computed_target_and_lag_imputed_flags():
    rows = []
    for day in (18, 19, 20):
        rows.append({
            "car_park_id": "tfnsw_gordon",
            "ts": f"2026-05-{day:02d}T08:00:00",
            "available": 163,
            "total_spots": 213,
        })
    frame = build_training_frame(rows)
    assert len(frame) == 3
    assert frame["target"].iloc[0] == pytest.approx(50 / 213, abs=1e-6)
    sorted_f = frame.sort_values("ts")
    assert sorted_f.iloc[0]["lag_24h_imputed"] == 1.0
    assert sorted_f.iloc[0]["lag_168h_imputed"] == 1.0
    last = sorted_f.iloc[-1]
    assert last["lag_24h"] == pytest.approx(50 / 213, abs=1e-6)
    assert last["lag_24h_imputed"] == 0.0
