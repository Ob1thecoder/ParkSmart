import json
import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.data.kml_loader import parse_kml
from app.data.seed_car_parks import seed as seed_car_parks
from app.db import get_connection, init_db
from app.scheduler import create_scheduler
from app.services.occupancy_service import backfill_sim_history

log = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")

_scheduler = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _scheduler
    log.info("Starting ParkSmart backend")

    # 1. Bootstrap database
    init_db(settings.db_path)
    log.info("Database ready at %s", settings.db_path)

    # 2. Seed car parks (idempotent)
    seed_car_parks(settings.db_path)
    log.info("Car parks seeded")

    # 3. Parse KML (if file exists)
    kml_path = Path(__file__).parent.parent.parent / "docs" / "willoughby_council_street_parking_signs_data.kml"
    if kml_path.exists():
        signs = parse_kml(kml_path, geocode=False)  # DISABLED: Takes 20min with geocode=True
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
                        s.lat, s.lon, s.street, s.raw_description,
                        json.dumps([e.model_dump() for e in s.signs]),
                        s.sign_photo_url,
                    )
                    for s in signs
                ],
            )
        log.info("Loaded %d parking signs", len(signs))
    else:
        log.warning("KML file not found at %s — skipping sign load", kml_path)

    # 4. Backfill 90 days of simulated history (idempotent — INSERT OR IGNORE)
    backfill_sim_history(settings.db_path, days=90)
    log.info("Sim history backfill complete")

    # 5. Start background scheduler
    _scheduler = create_scheduler(settings.db_path, settings)
    _scheduler.start()
    log.info("Scheduler started")

    yield

    if _scheduler and _scheduler.running:
        _scheduler.shutdown(wait=False)
    log.info("Shutting down ParkSmart backend")


app = FastAPI(title="ParkSmart API", version="0.2.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],    # restrict in production
    allow_methods=["*"],
    allow_headers=["*"],
)

from app.routers import occupancy, zones, predict, chat  # noqa: E402

app.include_router(occupancy.router, prefix="/api")
app.include_router(zones.router, prefix="/api")
app.include_router(predict.router, prefix="/api")
app.include_router(chat.router, prefix="/api")


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}
