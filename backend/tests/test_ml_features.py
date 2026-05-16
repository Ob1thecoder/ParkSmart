from datetime import datetime
import pytest
from app.ml.features import (
    FEATURE_COLUMNS,
    build_feature_row,
    build_training_frame,
)


def test_feature_row_has_all_columns():
    row = build_feature_row("tfnsw_gordon", datetime(2026, 5, 20, 14), 0.5, 0.6)
    assert set(row.keys()) == set(FEATURE_COLUMNS)


def test_feature_row_one_hot_car_park():
    gordon = build_feature_row("tfnsw_gordon", datetime(2026, 5, 20, 14), 0.5, 0.5)
    lindfield = build_feature_row("tfnsw_lindfield", datetime(2026, 5, 20, 14), 0.5, 0.5)
    assert gordon["is_gordon"] == 1.0 and gordon["is_lindfield"] == 0.0
    assert lindfield["is_lindfield"] == 1.0 and lindfield["is_gordon"] == 0.0


def test_feature_row_weekend_flag():
    saturday = build_feature_row("tfnsw_gordon", datetime(2026, 5, 23, 10), 0.5, 0.5)
    monday = build_feature_row("tfnsw_gordon", datetime(2026, 5, 25, 10), 0.5, 0.5)
    assert saturday["is_weekend"] == 1.0
    assert monday["is_weekend"] == 0.0


def test_feature_row_public_holiday_flag():
    # 2026-01-26 is Australia Day — a NSW public holiday
    holiday = build_feature_row("tfnsw_gordon", datetime(2026, 1, 26, 10), 0.5, 0.5)
    ordinary = build_feature_row("tfnsw_gordon", datetime(2026, 5, 20, 10), 0.5, 0.5)
    assert holiday["is_public_holiday"] == 1.0
    assert ordinary["is_public_holiday"] == 0.0


def test_feature_row_cyclical_bounds():
    row = build_feature_row("tfnsw_gordon", datetime(2026, 5, 20, 14), 0.5, 0.5)
    for key in ("hour_sin", "hour_cos", "dow_sin", "dow_cos"):
        assert -1.0001 <= row[key] <= 1.0001


def test_build_training_frame_empty():
    frame = build_training_frame([])
    assert list(frame.columns) == FEATURE_COLUMNS + ["target", "ts", "car_park_id"]
    assert len(frame) == 0


def test_build_training_frame_computes_target_and_lags():
    # Same hour across three days so lag_24h chains; 213-spot Gordon.
    rows = []
    for day in (18, 19, 20):
        for occupied in [50]:
            rows.append({
                "car_park_id": "tfnsw_gordon",
                "ts": f"2026-05-{day:02d}T08:00:00",
                "available": 213 - occupied,
                "total_spots": 213,
            })
    frame = build_training_frame(rows)
    assert len(frame) == 3
    # target = 1 - available/total = 50/213
    assert frame["target"].iloc[0] == pytest.approx(50 / 213, abs=1e-6)
    # the 2026-05-20 row should see 2026-05-19 as its lag_24h
    last = frame.sort_values("ts").iloc[-1]
    assert last["lag_24h"] == pytest.approx(50 / 213, abs=1e-6)
