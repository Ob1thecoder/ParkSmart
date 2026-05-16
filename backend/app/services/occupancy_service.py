import difflib
import logging
from datetime import datetime, timedelta, timezone
from pathlib import Path

from app.config import Settings
from app.data.seed_car_parks import ALL_CAR_PARKS, SIM_CAR_PARK_IDS, get_capacity, TFNSW_CAR_PARKS
from app.db import get_connection
from app.models import CarPark, OccupancyResponse
from app.services.simulator import simulated_available

log = logging.getLogger(__name__)

_NAME_INDEX: dict[str, CarPark] = {}
for _cp in ALL_CAR_PARKS:
    _NAME_INDEX[_cp.id.lower()] = _cp
    _NAME_INDEX[_cp.name.lower()] = _cp


def find_car_park(location: str) -> tuple[CarPark | None, list[str]]:
    """Fuzzy-match `location` to a car park. Returns (match, all_names)."""
    normalized = location.lower().strip()
    all_names = [cp.name for cp in ALL_CAR_PARKS]

    if normalized in _NAME_INDEX:
        return _NAME_INDEX[normalized], all_names

    matches = difflib.get_close_matches(normalized, _NAME_INDEX.keys(), n=1, cutoff=0.4)
    if matches:
        return _NAME_INDEX[matches[0]], all_names

    return None, all_names


def get_all_occupancy(db_path: Path, settings: Settings) -> list[OccupancyResponse]:
    """Return current occupancy for every car park. Reads history if available,
    falls back to on-demand computation for car parks with no history rows."""
    result = []
    with get_connection(db_path) as con:
        for cp in ALL_CAR_PARKS:
            row = con.execute(
                "SELECT ts, available, total_spots FROM occupancy_history "
                "WHERE car_park_id = ? ORDER BY ts DESC LIMIT 1",
                (cp.id,),
            ).fetchone()

            if row:
                available = row["available"]
                total = row["total_spots"]
                as_of = row["ts"]
            else:
                total = get_capacity(cp.id)
                if cp.source == "simulated":
                    available = simulated_available(cp.id, datetime.now())
                else:
                    available = total  # safe default: fully empty before first poll
                as_of = datetime.now().isoformat()

            occupied = total - available
            occ_pct = round(occupied / total, 4) if total > 0 else 0.0
            result.append(
                OccupancyResponse(
                    car_park_id=cp.id,
                    name=cp.name,
                    occupancy_pct=occ_pct,
                    occupied=occupied,
                    available=available,
                    capacity=total,
                    lat=cp.lat,
                    lon=cp.lon,
                    source=cp.source,
                    as_of=as_of,
                )
            )
    return result


def get_live_occupancy_tool(
    location: str, db_path: Path, settings: Settings
) -> dict:
    """LLM tool 1: get_live_occupancy. Returns the tool contract dict."""
    cp, candidates = find_car_park(location)
    if cp is None:
        return {"error": "no_match", "candidates": candidates}

    all_occ = get_all_occupancy(db_path, settings)
    occ = next((o for o in all_occ if o.car_park_id == cp.id), None)
    if occ is None:
        return {"error": "no_match", "candidates": candidates}

    return {
        "car_park_id": occ.car_park_id,
        "name": occ.name,
        "occupancy_pct": occ.occupancy_pct,
        "occupied": occ.occupied,
        "available": occ.available,
        "capacity": occ.capacity,
        "lat": occ.lat,
        "lon": occ.lon,
        "source": occ.source,
        "as_of": occ.as_of,
    }


def refresh_tfnsw(db_path: Path, settings: Settings) -> None:
    """Poll TfNSW full-list and upsert into occupancy_history. Called by scheduler."""
    from app.data.tfnsw_client import TfNSWClient

    with TfNSWClient(settings) as client:
        try:
            snapshots = client.get_full_list(fixture_name="full_list")
        except Exception as exc:
            log.warning("TfNSW full-list failed: %s", exc)
            return

    snap_by_fid = {s.facility_id: s for s in snapshots}
    with get_connection(db_path) as con:
        for cp in TFNSW_CAR_PARKS:
            snap = snap_by_fid.get(cp.tfnsw_facility_id)
            if snap is None:
                log.debug("No TfNSW data for facility %s (%s)", cp.tfnsw_facility_id, cp.id)
                continue
            con.execute(
                "INSERT OR REPLACE INTO occupancy_history "
                "(car_park_id, ts, available, total_spots) VALUES (?, ?, ?, ?)",
                (cp.id, snap.ts.isoformat(), snap.available, snap.total_spots),
            )
    log.info("TfNSW occupancy refreshed for %d facilities", len(snap_by_fid))


def refresh_sim(db_path: Path, dt: datetime | None = None) -> None:
    """Write one simulated snapshot per sim car park for the given hour. Called by scheduler."""
    if dt is None:
        dt = datetime.now(timezone.utc)
    dt = dt.replace(minute=0, second=0, microsecond=0)

    with get_connection(db_path) as con:
        for car_park_id in SIM_CAR_PARK_IDS:
            available = simulated_available(car_park_id, dt)
            capacity = get_capacity(car_park_id)
            con.execute(
                "INSERT OR IGNORE INTO occupancy_history "
                "(car_park_id, ts, available, total_spots) VALUES (?, ?, ?, ?)",
                (car_park_id, dt.isoformat(), available, capacity),
            )
    log.debug("Sim occupancy refreshed for %s", dt.isoformat())


def backfill_sim_history(db_path: Path, days: int = 90) -> None:
    """Seed the last `days` × 24 hourly rows for all sim car parks (idempotent)."""
    now = datetime.now(timezone.utc).replace(minute=0, second=0, microsecond=0)
    rows = []
    for car_park_id in SIM_CAR_PARK_IDS:
        capacity = get_capacity(car_park_id)
        for h in range(days * 24):
            dt = now - timedelta(hours=h)
            available = simulated_available(car_park_id, dt)
            rows.append((car_park_id, dt.isoformat(), available, capacity))

    with get_connection(db_path) as con:
        con.executemany(
            "INSERT OR IGNORE INTO occupancy_history "
            "(car_park_id, ts, available, total_spots) VALUES (?, ?, ?, ?)",
            rows,
        )
    log.info("Backfilled %d sim history rows (%d days)", len(rows), days)
