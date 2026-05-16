import pytest
from datetime import datetime
from pathlib import Path
from app.config import Settings
from app.services import occupancy_service
from app.models import OccupancyResponse, CarPark
from app.db import get_connection


def _make_settings(seeded_db: Path) -> Settings:
    return Settings(db_path=seeded_db, tfnsw_api_key="", anthropic_api_key="")


# --- get_all_occupancy ---

def test_get_all_occupancy_returns_seven_car_parks(seeded_db):
    settings = _make_settings(seeded_db)
    result = occupancy_service.get_all_occupancy(seeded_db, settings)
    assert len(result) == 7  # 5 sim + 2 tfnsw


def test_get_all_occupancy_response_shape(seeded_db):
    settings = _make_settings(seeded_db)
    for item in occupancy_service.get_all_occupancy(seeded_db, settings):
        assert isinstance(item, OccupancyResponse)
        assert 0.0 <= item.occupancy_pct <= 1.0
        assert item.available >= 0
        assert item.capacity > 0
        assert item.occupied + item.available == item.capacity


def test_get_all_occupancy_prefers_history_row(seeded_db):
    settings = _make_settings(seeded_db)
    # Insert a known row into occupancy_history
    with get_connection(seeded_db) as con:
        con.execute(
            "INSERT INTO occupancy_history (car_park_id, ts, available, total_spots) "
            "VALUES ('sim_westfield', '2026-05-11T10:00:00', 42, 1400)"
        )
    result = occupancy_service.get_all_occupancy(seeded_db, settings)
    westfield = next(r for r in result if r.car_park_id == "sim_westfield")
    assert westfield.available == 42
    assert westfield.as_of == "2026-05-11T10:00:00"


# --- find_car_park ---

def test_find_car_park_exact_name():
    cp, candidates = occupancy_service.find_car_park("Westfield Chatswood")
    assert cp is not None
    assert cp.id == "sim_westfield"


def test_find_car_park_fuzzy_partial():
    cp, candidates = occupancy_service.find_car_park("westfield")
    assert cp is not None
    assert cp.id == "sim_westfield"


def test_find_car_park_by_id():
    cp, candidates = occupancy_service.find_car_park("sim_mandarin_centre")
    assert cp is not None
    assert cp.id == "sim_mandarin_centre"


def test_find_car_park_no_match_returns_candidates():
    cp, candidates = occupancy_service.find_car_park("Completely Unknown Venue")
    assert cp is None
    assert len(candidates) > 0


# --- get_live_occupancy_tool ---

def test_get_live_occupancy_tool_success(seeded_db):
    settings = _make_settings(seeded_db)
    result = occupancy_service.get_live_occupancy_tool("Westfield", seeded_db, settings)
    assert "error" not in result
    assert result["car_park_id"] == "sim_westfield"
    assert "occupancy_pct" in result
    assert "lat" in result


def test_get_live_occupancy_tool_no_match(seeded_db):
    settings = _make_settings(seeded_db)
    result = occupancy_service.get_live_occupancy_tool("NotARealPlace", seeded_db, settings)
    assert result["error"] == "no_match"
    assert "candidates" in result


# --- refresh_sim ---

def test_refresh_sim_writes_occupancy_history(seeded_db):
    settings = _make_settings(seeded_db)
    dt = datetime(2026, 5, 11, 14, 0, 0)
    occupancy_service.refresh_sim(seeded_db, dt=dt)
    with get_connection(seeded_db) as con:
        rows = con.execute(
            "SELECT count(*) as n FROM occupancy_history WHERE ts LIKE '2026-05-11T14%'"
        ).fetchone()
    assert rows["n"] == 5  # one row per sim car park


def test_refresh_sim_is_idempotent(seeded_db):
    settings = _make_settings(seeded_db)
    dt = datetime(2026, 5, 11, 15, 0, 0)
    occupancy_service.refresh_sim(seeded_db, dt=dt)
    occupancy_service.refresh_sim(seeded_db, dt=dt)  # second call must not raise
    with get_connection(seeded_db) as con:
        count = con.execute(
            "SELECT count(*) as n FROM occupancy_history WHERE car_park_id='sim_westfield'"
        ).fetchone()["n"]
    assert count == 1  # INSERT OR IGNORE: still just one row


# --- backfill_sim_history ---

def test_backfill_inserts_rows_for_all_sim_parks(seeded_db):
    occupancy_service.backfill_sim_history(seeded_db, days=2)
    with get_connection(seeded_db) as con:
        count = con.execute(
            "SELECT count(*) as n FROM occupancy_history"
        ).fetchone()["n"]
    # 5 sim parks × 2 days × 24 hours = 240 rows
    assert count == 240
