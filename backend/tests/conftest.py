import pytest
from pathlib import Path
from app.db import init_db, get_connection
from app.data.seed_car_parks import seed as _seed_car_parks


@pytest.fixture
def db_path(tmp_path: Path) -> Path:
    path = tmp_path / "test.db"
    init_db(path)
    return path


@pytest.fixture
def conn(db_path: Path):
    with get_connection(db_path) as con:
        yield con


@pytest.fixture
def seeded_db(db_path: Path) -> Path:
    """DB with schema initialised AND all car parks seeded."""
    _seed_car_parks(db_path)
    return db_path
