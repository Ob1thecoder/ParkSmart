from fastapi import APIRouter, Depends
from app.config import Settings, get_settings
from app.models import OccupancyResponse
from app.services import occupancy_service

router = APIRouter()


@router.get("/occupancy", response_model=list[OccupancyResponse])
def list_occupancy(settings: Settings = Depends(get_settings)) -> list[OccupancyResponse]:
    return occupancy_service.get_all_occupancy(settings.db_path, settings)
