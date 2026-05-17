import re
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Optional, Union

from app.config import settings

try:
    import psycopg2
    import psycopg2.extras
    HAS_PSYCOPG2 = True
except ImportError:
    HAS_PSYCOPG2 = False


_SCHEMA_SQLITE = """
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

CREATE INDEX IF NOT EXISTS idx_signs_street
    ON parking_signs(LOWER(street));
"""

_SCHEMA_POSTGRES = """
CREATE TABLE IF NOT EXISTS car_parks (
    id                TEXT PRIMARY KEY,
    name              TEXT NOT NULL,
    lat               DOUBLE PRECISION NOT NULL,
    lon               DOUBLE PRECISION NOT NULL,
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
    id               SERIAL PRIMARY KEY,
    raw_sign_id      TEXT,
    lat              DOUBLE PRECISION NOT NULL,
    lon              DOUBLE PRECISION NOT NULL,
    street           TEXT,
    raw_description  TEXT NOT NULL,
    sign_categories  TEXT NOT NULL,
    sign_photo_url   TEXT
);

CREATE INDEX IF NOT EXISTS idx_signs_street
    ON parking_signs(LOWER(street));
"""


class DBConnection:
    """Unified database connection wrapper for SQLite and PostgreSQL."""

    def __init__(self, conn, is_postgres: bool):
        self._conn = conn
        self._is_postgres = is_postgres

    def _convert_sql(self, sql: str) -> str:
        """Convert SQLite SQL syntax to PostgreSQL if needed."""
        if not self._is_postgres:
            return sql

        result = re.sub(r'\?', '%s', sql)
        result = re.sub(r'INSERT OR IGNORE', 'INSERT', result, flags=re.IGNORECASE)
        result = re.sub(r'INSERT OR REPLACE', 'INSERT', result, flags=re.IGNORECASE)

        if 'INSERT' in result.upper() and 'ON CONFLICT' not in result.upper():
            if 'INSERT OR IGNORE' in sql.upper():
                result = result.rstrip(';').rstrip() + ' ON CONFLICT DO NOTHING'
            elif 'INSERT OR REPLACE' in sql.upper():
                pass

        result = re.sub(r'julianday\(([^)]+)\)', r"EXTRACT(EPOCH FROM \1::timestamp)", result)

        return result

    def execute(self, sql: str, params=None):
        sql = self._convert_sql(sql)
        cur = self._conn.cursor()
        if params:
            cur.execute(sql, params)
        else:
            cur.execute(sql)
        return cur

    def executemany(self, sql: str, params_list):
        sql = self._convert_sql(sql)
        cur = self._conn.cursor()
        if self._is_postgres:
            psycopg2.extras.execute_batch(cur, sql, params_list)
        else:
            cur.executemany(sql, params_list)
        return cur

    def executescript(self, script: str):
        if self._is_postgres:
            cur = self._conn.cursor()
            for stmt in script.split(';'):
                stmt = stmt.strip()
                if stmt and not stmt.upper().startswith('PRAGMA'):
                    cur.execute(stmt)
        else:
            self._conn.executescript(script)

    def commit(self):
        self._conn.commit()

    def rollback(self):
        self._conn.rollback()

    def close(self):
        self._conn.close()


def init_db(db_path: Optional[Path] = None) -> None:
    """Initialize database schema."""
    with get_connection(db_path) as con:
        if settings.use_postgres:
            con.executescript(_SCHEMA_POSTGRES)
        else:
            con.executescript(_SCHEMA_SQLITE)


@contextmanager
def get_connection(db_path: Optional[Union[Path, str]] = None):
    """Get a database connection (PostgreSQL if DATABASE_URL set, else SQLite)."""
    if settings.use_postgres and HAS_PSYCOPG2:
        conn = psycopg2.connect(
            settings.database_url,
            cursor_factory=psycopg2.extras.RealDictCursor
        )
        wrapped = DBConnection(conn, is_postgres=True)
    else:
        path = db_path or settings.db_path
        conn = sqlite3.connect(str(path), detect_types=sqlite3.PARSE_DECLTYPES)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys=ON")
        wrapped = DBConnection(conn, is_postgres=False)

    try:
        yield wrapped
        wrapped.commit()
    except Exception:
        wrapped.rollback()
        raise
    finally:
        wrapped.close()
