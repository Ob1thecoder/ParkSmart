import logging
from pathlib import Path

from apscheduler.schedulers.background import BackgroundScheduler

from app.config import Settings
from app.services import occupancy_service

log = logging.getLogger(__name__)


def create_scheduler(db_path: Path, settings: Settings) -> BackgroundScheduler:
    scheduler = BackgroundScheduler()

    scheduler.add_job(
        func=occupancy_service.refresh_tfnsw,
        trigger="interval",
        seconds=300,       # every 5 minutes
        id="tfnsw_poll",
        kwargs={"db_path": db_path, "settings": settings},
        replace_existing=True,
    )

    scheduler.add_job(
        func=occupancy_service.refresh_sim,
        trigger="interval",
        seconds=3600,      # every 1 hour
        id="sim_refresh",
        kwargs={"db_path": db_path},
        replace_existing=True,
    )

    return scheduler
