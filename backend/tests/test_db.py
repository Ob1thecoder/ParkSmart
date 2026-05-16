import sqlite3
import pytest
from pathlib import Path
from app.db import init_db, get_connection


def test_init_creates_required_tables(db_path: Path):
    with get_connection(db_path) as con:
        cur = con.execute(
            "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
        )
        tables = {row[0] for row in cur.fetchall()}
    assert tables >= {"car_parks", "occupancy_history", "parking_signs"}


def test_init_is_idempotent(db_path: Path):
    # Calling init_db twice must not raise or corrupt data
    init_db(db_path)
    with get_connection(db_path) as con:
        con.execute("SELECT count(*) FROM car_parks").fetchone()


def test_foreign_key_enforcement(db_path: Path):
    with get_connection(db_path) as con:
        with pytest.raises(sqlite3.IntegrityError):
            con.execute(
                "INSERT INTO occupancy_history "
                "(car_park_id, ts, available, total_spots) "
                "VALUES ('nonexistent_id', datetime('now'), 100, 200)"
            )


def test_occupancy_history_primary_key(db_path: Path):
    with get_connection(db_path) as con:
        con.execute(
            "INSERT INTO car_parks (id, name, lat, lon, source) "
            "VALUES ('test_cp', 'Test', -33.7, 151.1, 'simulated')"
        )
        con.execute(
            "INSERT INTO occupancy_history (car_park_id, ts, available, total_spots) "
            "VALUES ('test_cp', '2026-05-11T10:00:00', 100, 200)"
        )
        con.commit()
        with pytest.raises(sqlite3.IntegrityError):
            con.execute(
                "INSERT INTO occupancy_history (car_park_id, ts, available, total_spots) "
                "VALUES ('test_cp', '2026-05-11T10:00:00', 99, 200)"
            )


def test_parking_signs_has_sign_categories_column(db_path: Path):
    with get_connection(db_path) as con:
        con.execute(
            "INSERT INTO parking_signs (lat, lon, raw_description, sign_categories) "
            "VALUES (-33.795, 151.183, 'test', '[{\"category\":\"No Stopping\"}]')"
        )
        row = con.execute("SELECT sign_categories FROM parking_signs LIMIT 1").fetchone()
    assert "No Stopping" in row["sign_categories"]
