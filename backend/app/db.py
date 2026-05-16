import sqlite3
from contextlib import contextmanager
from pathlib import Path


_SCHEMA = """
PRAGMA journal_mode=WAL;
PRAGMA foreign_keys=ON;

CREATE TABLE IF NOT EXISTS car_parks (
    id                TEXT PRIMARY KEY,
    name              TEXT NOT NULL,
    lat               REAL NOT NULL,
    lon               REAL NOT NULL,
    suburb            TEXT,
    address           TEXT,
    source            TEXT NOT NULL CHECK(source IN ('tfnsw', 'simulated')),
    tfnsw_facility_id TEXT
);

CREATE TABLE IF NOT EXISTS occupancy_history (
    car_park_id  TEXT NOT NULL REFERENCES car_parks(id),
    ts           TEXT NOT NULL,
    available    INTEGER NOT NULL,
    total_spots  INTEGER NOT NULL,
    PRIMARY KEY (car_park_id, ts)
);

CREATE INDEX IF NOT EXISTS idx_occ_ts ON occupancy_history(ts);

CREATE TABLE IF NOT EXISTS parking_signs (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    raw_sign_id      TEXT,
    lat              REAL NOT NULL,
    lon              REAL NOT NULL,
    street           TEXT,
    raw_description  TEXT NOT NULL,
    sign_categories  TEXT NOT NULL,
    sign_photo_url   TEXT
);

-- sign_categories is a JSON array: [{"category":"No Stopping","direction":"both","description":""}]
-- street is populated by reverse geocoding at first load; NULL if geocoder unavailable.
CREATE INDEX IF NOT EXISTS idx_signs_street
    ON parking_signs(LOWER(street));
"""


def init_db(db_path: Path) -> None:
    with get_connection(db_path) as con:
        con.executescript(_SCHEMA)


@contextmanager
def get_connection(db_path: Path):
    con = sqlite3.connect(str(db_path), detect_types=sqlite3.PARSE_DECLTYPES)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA foreign_keys=ON")
    try:
        yield con
        con.commit()
    except Exception:
        con.rollback()
        raise
    finally:
        con.close()
