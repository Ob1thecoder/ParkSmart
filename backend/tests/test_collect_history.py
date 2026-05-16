from datetime import date
from app.config import Settings
from app.db import get_connection
from app.ml.collect_history import collect_history


def test_collect_history_inserts_rows(seeded_db):
    settings = Settings(db_path=seeded_db, tfnsw_api_key="")
    stats = collect_history(
        seeded_db, settings, days=3, today=date(2026, 5, 20), fixture_name="history_sample"
    )
    assert stats["rows_inserted"] == 6  # 3 per car park (fixed fixture timestamps)
    assert stats["by_car_park"]["tfnsw_gordon"] == 3
    assert stats["by_car_park"]["tfnsw_lindfield"] == 3


def test_collect_history_writes_tfnsw_car_park_ids(seeded_db):
    settings = Settings(db_path=seeded_db, tfnsw_api_key="")
    collect_history(
        seeded_db, settings, days=2, today=date(2026, 5, 20), fixture_name="history_sample"
    )
    with get_connection(seeded_db) as con:
        rows = con.execute(
            "SELECT DISTINCT car_park_id FROM occupancy_history "
            "WHERE car_park_id LIKE 'tfnsw_%'"
        ).fetchall()
    ids = {r["car_park_id"] for r in rows}
    assert ids == {"tfnsw_gordon", "tfnsw_lindfield"}


def test_collect_history_is_idempotent(seeded_db):
    settings = Settings(db_path=seeded_db, tfnsw_api_key="")
    kwargs = dict(days=3, today=date(2026, 5, 20), fixture_name="history_sample")
    collect_history(seeded_db, settings, **kwargs)
    stats2 = collect_history(seeded_db, settings, **kwargs)
    assert stats2["rows_inserted"] == 0  # all rows already present
