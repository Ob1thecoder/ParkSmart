import logging
import json as _json
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.config import settings
from app.db import init_db, get_connection
from app.data.seed_car_parks import seed as seed_car_parks
from app.data.kml_loader import parse_kml

log = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")


@asynccontextmanager
async def lifespan(app: FastAPI):
    log.info("Starting ParkSmart backend")

    # 1. Bootstrap database
    init_db(settings.db_path)
    log.info("Database ready at %s", settings.db_path)

    # 2. Seed car parks (idempotent)
    seed_car_parks(settings.db_path)
    log.info("Car parks seeded")

    # 3. Parse KML (if file exists)
    kml_path = settings.fixtures_dir.parent / "willoughby_parking.kml"
    if kml_path.exists():
        signs = parse_kml(kml_path, geocode=True)
        with get_connection(settings.db_path) as con:
            con.executemany(
                """
                INSERT OR IGNORE INTO parking_signs
                    (raw_sign_id, lat, lon, street, raw_description, sign_categories, sign_photo_url)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    (
                        s.raw_sign_id,
                        s.lat,
                        s.lon,
                        s.street,
                        s.raw_description,
                        _json.dumps([e.model_dump() for e in s.signs]),
                        s.sign_photo_url,
                    )
                    for s in signs
                ],
            )
        log.info("Loaded %d parking signs", len(signs))
    else:
        log.warning("KML file not found at %s — skipping sign load", kml_path)

    yield

    log.info("Shutting down ParkSmart backend")


app = FastAPI(title="ParkSmart API", version="0.1.0", lifespan=lifespan)


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}
