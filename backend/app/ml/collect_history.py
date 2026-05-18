"""
TfNSW history collection — backfills occupancy into `occupancy_history` for every
seeded TfNSW facility (see `app.data.seed_car_parks.TFNSW_CAR_PARKS`).

Training consumes site-agnostic features across **all** seeded car parks that have rows.

Run:  python -m app.ml.collect_history --days 120
Requires TFNSW_API_KEY in .env to fetch real data. Without a key the underlying
client falls back to fixtures.
"""
import argparse
import logging
from datetime import date, datetime, timedelta
from pathlib import Path

from app.config import Settings, settings as _settings
from app.data.seed_car_parks import TFNSW_CAR_PARKS
from app.data.tfnsw_client import TfNSWClient
from app.db import get_connection

log = logging.getLogger(__name__)


def collect_history(
    db_path: Path,
    settings: Settings,
    days: int,
    today: date | None = None,
    fixture_name: str | None = None,
) -> dict:
    """
    Pull `days` calendar days of TfNSW history for every TfNSW car park and
    insert hourly snapshots into occupancy_history (idempotent).

    Returns {"rows_inserted": int, "by_car_park": {car_park_id: int}}.
    """
    if today is None:
        today = datetime.now().date()

    by_car_park: dict[str, int] = {}
    with TfNSWClient(settings) as client:
        with get_connection(db_path) as con:
            for cp in TFNSW_CAR_PARKS:
                inserted = 0
                for offset in range(1, days + 1):
                    event_date = today - timedelta(days=offset)
                    try:
                        snapshots = client.get_history(
                            cp.tfnsw_facility_id, event_date, fixture_name=fixture_name
                        )
                    except FileNotFoundError:
                        continue
                    except Exception as exc:  # noqa: BLE001 — log and skip a bad day
                        log.warning("history fetch failed %s %s: %s", cp.id, event_date, exc)
                        continue
                    for snap in snapshots:
                        cur = con.execute(
                            "INSERT OR IGNORE INTO occupancy_history "
                            "(car_park_id, ts, available, total_spots) VALUES (?, ?, ?, ?)",
                            (cp.id, snap.ts.isoformat(), snap.available, snap.total_spots),
                        )
                        inserted += cur.rowcount
                by_car_park[cp.id] = inserted
                log.info("Collected %d new rows for %s", inserted, cp.id)

    return {"rows_inserted": sum(by_car_park.values()), "by_car_park": by_car_park}


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    parser = argparse.ArgumentParser(description="Backfill TfNSW car park history.")
    parser.add_argument("--days", type=int, default=120, help="How many days back to fetch")
    args = parser.parse_args()

    stats = collect_history(_settings.db_path, _settings, days=args.days)
    print(f"Inserted {stats['rows_inserted']} new rows")
    for cp_id, n in stats["by_car_park"].items():
        print(f"  {cp_id}: {n}")


if __name__ == "__main__":
    main()
