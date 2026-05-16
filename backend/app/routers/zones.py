from fastapi import APIRouter, Depends, HTTPException, Query
from app.config import Settings, get_settings
from app.services import zone_service

router = APIRouter()


@router.get("/zones")
def get_zones(
    street: str = Query(..., description="Street name in Chatswood CBD"),
    settings: Settings = Depends(get_settings),
) -> dict:
    result = zone_service.get_zone_restrictions(street, settings.db_path)
    if "error" in result and result["error"] == "not_found":
        raise HTTPException(status_code=404, detail=f"No zone data found for '{street}'")
    return result
