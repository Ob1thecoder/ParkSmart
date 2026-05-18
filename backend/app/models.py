from datetime import datetime
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field


class CarPark(BaseModel):
    id: str
    name: str
    lat: float
    lon: float
    suburb: str | None = None
    address: str | None = None
    source: Literal["tfnsw", "simulated"]
    tfnsw_facility_id: str | None = None
    # From seed metadata only — not persisted on car_parks table
    venue_type: Literal["commuter", "retail"] = "commuter"
    # Not stored in DB — computed from latest occupancy_history row
    total_spots: int = 0


class OccupancySnapshot(BaseModel):
    car_park_id: str
    ts: datetime
    available: int
    total_spots: int

    @property
    def occupancy_pct(self) -> float:
        if self.total_spots == 0:
            return 0.0
        return round(1.0 - self.available / self.total_spots, 4)


class SignEntry(BaseModel):
    """One sign panel on a sign post (up to 4 per post in the Willoughby KML)."""
    category: str    # "No Stopping", "No Parking", "Restricted Parking", etc.
    direction: str   # "left", "right", "both", "none"
    description: str # time/duration: "Max Dur. 1 hour 8:30a - 6:00p M-F; ..."


class ParkingSignRecord(BaseModel):
    """
    One sign post from the Willoughby Council KML.
    street is populated by reverse geocoding after parse; None if geocoder unavailable.
    """
    model_config = ConfigDict(frozen=False)  # allow street to be set post-construction

    raw_sign_id: str | None = None
    lat: float
    lon: float
    street: str | None = None
    raw_description: str
    signs: list[SignEntry]      # extracted from sign1_category … sign4_category fields
    sign_photo_url: str | None = None


# RestrictionRule is used by zone_service (Plan 2) and seed_zones.json.
# It represents a parsed time/day rule derived from SignEntry.description.
class RestrictionRule(BaseModel):
    days: list[str]
    start: str           # "HH:MM"
    end: str             # "HH:MM"
    max_minutes: int | None = None
    type: Literal["no_stopping", "no_parking", "timed", "permit_only", "loading", "other"]


class PredictionResult(BaseModel):
    car_park_id: str
    name: str
    predicted_occupancy_pct: float = Field(ge=0.0, le=1.0)
    confidence: float = Field(ge=0.0, le=1.0)
    target_datetime: datetime
    model_version: str


class OccupancyResponse(BaseModel):
    """API + LLM tool response for a single car park's current occupancy."""
    car_park_id: str
    name: str
    occupancy_pct: float          # 0.0–1.0
    occupied: int
    available: int
    capacity: int
    lat: float
    lon: float
    source: Literal["tfnsw", "simulated"]
    as_of: str                    # ISO8601 string as stored in DB


class ZoneSegment(BaseModel):
    """One group of signs on the same side of a street."""
    side: str | None = None       # "left" | "right" | null (both/unknown)
    rules_plain_english: str
    rules_structured: list[RestrictionRule] = []
    sign_photo_url: str | None = None


class ZoneResponse(BaseModel):
    street: str
    segments: list[ZoneSegment]


class ChatRequest(BaseModel):
    message: str
    history: list[dict] = []     # [{role: "user"|"assistant", content: str}]
