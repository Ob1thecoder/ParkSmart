"""
Static seed data for ParkSmart car parks.

DATA AUDIT FINDING: Chatswood CBD has NO entries in the TfNSW Car Park API.
The API covers commuter Park&Ride facilities; the nearest North Shore entries
are Gordon (#6) and Lindfield (#34).

Consequence:
  - All Chatswood CBD and nearby retail car parks in this app are source="simulated".
  - Gordon is seeded as source="tfnsw" and used for:
      a) A live real-data marker on the map (labelled, ~3km from Chatswood CBD)
      b) ML model training data via get_history() (commuter pattern proxy)

The TfNSW facility_id values match the 'facility_id' field in the API response
(a simple integer string, e.g. "6"), NOT the composite `tfnsw_facility_id` TPR code.

Full facility list sourced from TfNSW Car Parks documentation (`app.data.tfnsw_facility_seed`).
The occupancy model is **site-agnostic** (fixed feature schema): all seeded car parks can
contribute rows from ``occupancy_history``; ``venue_type`` + capacity encode generic context.
"""
from app.models import CarPark
from app.db import get_connection

from app.data.tfnsw_facility_seed import (
    TFNSW_LEGACY_ADDRESS_OVERRIDES,
    TFNSW_LEGACY_IDS,
    TFNSW_LEGACY_NAME_OVERRIDES,
    TFNSW_SEED_ROWS,
    slug_address,
)

# Chatswood CBD car parks — all simulated (not in TfNSW feed)
CHATSWOOD_CAR_PARKS: list[CarPark] = [
    CarPark(
        id="sim_westfield",
        name="Westfield Chatswood",
        lat=-33.7972,
        lon=151.1825,
        suburb="Chatswood",
        address="1 Anderson Street, Chatswood NSW 2067",
        source="simulated",
        venue_type="retail",
        total_spots=1400,
    ),
    CarPark(
        id="sim_chatswood_chase",
        name="Chatswood Chase",
        lat=-33.7964,
        lon=151.1799,
        suburb="Chatswood",
        address="345 Victoria Avenue, Chatswood NSW 2067",
        source="simulated",
        venue_type="retail",
        total_spots=850,
    ),
    CarPark(
        id="sim_mandarin_centre",
        name="Mandarin Centre",
        lat=-33.7992,
        lon=151.1804,
        suburb="Chatswood",
        address="1 Albert Avenue, Chatswood NSW 2067",
        source="simulated",
        venue_type="retail",
        total_spots=280,
    ),
    CarPark(
        id="sim_victoria_ave_cp",
        name="Victoria Avenue Car Park",
        lat=-33.7975,
        lon=151.1810,
        suburb="Chatswood",
        address="Victoria Avenue, Chatswood NSW 2067",
        source="simulated",
        venue_type="commuter",
        total_spots=160,
    ),
    CarPark(
        id="sim_chatswood_west_cp",
        name="Chatswood West Car Park",
        lat=-33.7968,
        lon=151.1788,
        suburb="Chatswood",
        address="Help Street, Chatswood NSW 2067",
        source="simulated",
        venue_type="retail",
        total_spots=320,
    ),
    # Extra North Shore commuter / retail garages (TfNSW does not expose them on the carpark feed)
    CarPark(
        id="sim_artarmon_hampden",
        name="Artarmon Hampden Shops",
        lat=-33.8102,
        lon=151.1554,
        suburb="Artarmon",
        address="Hampden Road, Artarmon NSW 2064",
        source="simulated",
        venue_type="commuter",
        total_spots=210,
    ),
    CarPark(
        id="sim_st_leonards_plaza",
        name="St Leonards Railway Plaza Parking",
        lat=-33.8225,
        lon=151.1942,
        suburb="St Leonards",
        address="Railway Crescent, St Leonards NSW 2065",
        source="simulated",
        venue_type="commuter",
        total_spots=340,
    ),
    CarPark(
        id="sim_roseville_royal_st",
        name="Royal Street Roseville Parking",
        lat=-33.7843,
        lon=151.1871,
        suburb="Roseville",
        address="Royal Street, Roseville NSW 2069",
        source="simulated",
        venue_type="commuter",
        total_spots=140,
    ),
]

def _build_tfnsw_car_parks() -> list[CarPark]:
    out: list[CarPark] = []
    for fid, name, lat, lon, suburb, spots in TFNSW_SEED_ROWS:
        pk = TFNSW_LEGACY_IDS.get(fid) or f"tfnsw_facility_{fid}"
        display_name = TFNSW_LEGACY_NAME_OVERRIDES.get(fid, name)
        address = TFNSW_LEGACY_ADDRESS_OVERRIDES.get(fid, slug_address(display_name, suburb))
        out.append(
            CarPark(
                id=pk,
                name=display_name,
                lat=lat,
                lon=lon,
                suburb=suburb,
                address=address,
                source="tfnsw",
                tfnsw_facility_id=fid,
                venue_type="commuter",
                total_spots=spots,
            )
        )
    return out


# Real TfNSW facilities — live data display + contribute rows to site-agnostic ML training.
TFNSW_CAR_PARKS: list[CarPark] = _build_tfnsw_car_parks()

ALL_CAR_PARKS: list[CarPark] = CHATSWOOD_CAR_PARKS + TFNSW_CAR_PARKS

_TOTAL_SPOTS: dict[str, int] = {cp.id: cp.total_spots for cp in ALL_CAR_PARKS}

SIM_CAR_PARK_IDS: list[str] = [cp.id for cp in CHATSWOOD_CAR_PARKS]


def get_capacity(car_park_id: str) -> int:
    return _TOTAL_SPOTS[car_park_id]


def seed(db_path) -> None:
    """Insert all car parks if they don't already exist (idempotent)."""
    with get_connection(db_path) as con:
        for cp in ALL_CAR_PARKS:
            con.execute(
                """
                INSERT OR IGNORE INTO car_parks
                    (id, name, lat, lon, suburb, address, source, tfnsw_facility_id)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    cp.id, cp.name, cp.lat, cp.lon,
                    cp.suburb, cp.address, cp.source, cp.tfnsw_facility_id,
                ),
            )
