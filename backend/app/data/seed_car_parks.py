"""
Static seed data for ParkSmart car parks.

DATA AUDIT FINDING: Chatswood CBD has NO entries in the TfNSW Car Park API.
The API covers commuter Park&Ride facilities; the nearest North Shore entries
are Gordon (#6) and Lindfield (#34).

Consequence:
  - All 5 Chatswood CBD car parks are source="simulated".
  - Gordon is seeded as source="tfnsw" and used for:
      a) A live real-data marker on the map (labelled, ~3km from Chatswood CBD)
      b) ML model training data via get_history() (commuter pattern proxy)

The TfNSW facility_id values match the 'facility_id' field in the API response
(a simple integer string, e.g. "6"), NOT the TSN or tfnsw_facility_id composite.
"""
from app.models import CarPark
from app.db import get_connection

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
        total_spots=320,
    ),
]

# Real TfNSW facilities — used for live data display and ML training.
TFNSW_CAR_PARKS: list[CarPark] = [
    CarPark(
        id="tfnsw_gordon",
        name="Park&Ride - Gordon",
        lat=-33.756009,
        lon=151.154528,
        suburb="Gordon",
        address="Henry Street, Gordon NSW 2072",
        source="tfnsw",
        tfnsw_facility_id="6",
        total_spots=213,
    ),
    CarPark(
        id="tfnsw_lindfield",
        name="Park&Ride - Lindfield",
        lat=-33.775185,
        lon=151.169111,
        suburb="Lindfield",
        address="Village Green, Lindfield NSW 2070",
        source="tfnsw",
        tfnsw_facility_id="34",
        total_spots=94,
    ),
]

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
