from fastapi import APIRouter, Depends, HTTPException, Query
from app.config import Settings, get_settings
from app.services import prediction_service

router = APIRouter()


@router.get("/predict")
def predict(
    location: str = Query(..., description="Car park name or nearby landmark"),
    target_datetime: str = Query(..., description="ISO8601 datetime, within next 7 days"),
    settings: Settings = Depends(get_settings),
) -> dict:
    result = prediction_service.predict_availability_tool(
        location, target_datetime, settings.db_path
    )
    if "error" in result:
        error = result["error"]
        if error == "no_match":
            raise HTTPException(status_code=404, detail=result)
        raise HTTPException(status_code=422, detail=result)
    return result
