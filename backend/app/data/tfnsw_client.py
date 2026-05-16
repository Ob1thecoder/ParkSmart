"""
TfNSW Car Park API client.

Implements all four endpoints from carparkswagger_prod_2.yaml:
  GET /v1/carpark                    → get_facility_list()   (discovery)
  GET /v1/carpark?facility=<id>      → get_occupancy()       (single live)
  GET /v1/carpark/full-list          → get_full_list()       (all live, for scheduler)
  GET /v1/carpark/history            → get_history()         (ML training data)

Auth: Authorization: apikey <TOKEN>  (per Swagger securityDefinitions)

Response field names are undocumented (schema: type: file in the Swagger).
All _parse_* methods use best-guess keys. Update them after the Day 1
data audit by replacing fixture files with real recorded responses and
adjusting field names to match.
"""
import json
import logging
from dataclasses import dataclass
from datetime import date, datetime, timezone
from pathlib import Path

import httpx

from app.config import Settings

log = logging.getLogger(__name__)

TFNSW_BASE = "https://api.transport.nsw.gov.au/v1/carpark"


@dataclass
class TfNSWSnapshot:
    facility_id: str
    available: int
    occupied: int
    total_spots: int
    ts: datetime


class TfNSWClient:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._api_key = (settings.tfnsw_api_key or "").strip()
        self._http = httpx.Client(
            headers={"Authorization": f"apikey {self._api_key}"},
            timeout=10.0,
        )

    # ------------------------------------------------------------------
    # Public methods
    # ------------------------------------------------------------------

    def get_occupancy(self, facility_id: str, *, fixture_name: str) -> TfNSWSnapshot:
        """Live occupancy for one facility. Falls back to fixture on error or missing key."""
        if self._api_key:
            try:
                resp = self._http.get(TFNSW_BASE, params={"facility": facility_id})
                resp.raise_for_status()
                snap = self._parse_snapshot(resp.json())
                snap.facility_id = facility_id
                return snap
            except httpx.HTTPError as exc:
                log.warning("TfNSW get_occupancy error (%s), falling back: %s", facility_id, exc)
        snap = self._load_fixture_snapshot(fixture_name)
        snap.facility_id = facility_id
        return snap

    def get_full_list(self, *, fixture_name: str = "full_list") -> list[TfNSWSnapshot]:
        """
        Live occupancy for all facilities in one call.
        Preferred over get_occupancy() for the scheduler — fewer round trips.
        """
        if self._api_key:
            try:
                resp = self._http.get(f"{TFNSW_BASE}/full-list")
                resp.raise_for_status()
                return self._parse_snapshot_list(resp.json())
            except httpx.HTTPError as exc:
                log.warning("TfNSW get_full_list error, falling back: %s", exc)
        return self._load_fixture_snapshot_list(fixture_name)

    def get_facility_list(self, *, fixture_name: str = "facility_list") -> list[dict]:
        """
        Returns raw facility discovery list (IDs + names). Used once at startup
        to find which facility_id corresponds to Chatswood car parks.
        Returns raw dicts because field names are unknown until the data audit.
        """
        if self._api_key:
            try:
                resp = self._http.get(TFNSW_BASE)
                resp.raise_for_status()
                data = resp.json()
                return data if isinstance(data, list) else [data]
            except httpx.HTTPError as exc:
                log.warning("TfNSW get_facility_list error, falling back: %s", exc)
        return self._load_fixture_raw(fixture_name)

    def get_history(
        self,
        facility_id: str,
        event_date: date,
        *,
        fixture_name: str | None = None,
    ) -> list[TfNSWSnapshot]:
        """
        Historical occupancy for one facility on one calendar day.
        Used by the ML training batch script (Plan 3).
        fixture_name defaults to 'history_{facility_id}_{date}' when None.
        """
        if fixture_name is None:
            fixture_name = f"history_{facility_id}_{event_date.isoformat()}"

        if self._api_key:
            try:
                resp = self._http.get(
                    f"{TFNSW_BASE}/history",
                    params={"facility": facility_id, "eventdate": event_date.isoformat()},
                )
                resp.raise_for_status()
                return self._parse_snapshot_list(resp.json())
            except httpx.HTTPError as exc:
                log.warning(
                    "TfNSW get_history error (%s %s), falling back: %s",
                    facility_id, event_date, exc,
                )
        return self._load_fixture_snapshot_list(fixture_name)

    def close(self) -> None:
        self._http.close()

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()

    # ------------------------------------------------------------------
    # Parsing helpers
    # ------------------------------------------------------------------

    def _parse_snapshot(self, data: dict) -> TfNSWSnapshot:
        # spots         — string, total capacity
        # occupancy.total — string, vehicles currently IN the car park
        # available     — derived: int(spots) - int(occupancy.total)
        # MessageDate   — naive datetime string
        total = int(data.get("spots", 0))
        occupied = int((data.get("occupancy") or {}).get("total", 0))
        available = max(0, total - occupied)

        raw_ts = data.get("MessageDate", "")
        try:
            ts = datetime.fromisoformat(raw_ts)
        except (ValueError, TypeError):
            ts = datetime.now(tz=timezone.utc)

        return TfNSWSnapshot(
            facility_id=str(data.get("facility_id", "")),
            available=available,
            occupied=occupied,
            total_spots=total,
            ts=ts,
        )

    def _parse_snapshot_list(self, data) -> list[TfNSWSnapshot]:
        if isinstance(data, list):
            return [self._parse_snapshot(item) for item in data]
        for key in ("car_parks", "facilities", "data", "results"):
            if key in data:
                return [self._parse_snapshot(item) for item in data[key]]
        return [self._parse_snapshot(data)]

    # ------------------------------------------------------------------
    # Fixture loaders
    # ------------------------------------------------------------------

    def _load_fixture_snapshot(self, fixture_name: str) -> TfNSWSnapshot:
        return self._parse_snapshot(self._read_fixture_json(fixture_name))

    def _load_fixture_snapshot_list(self, fixture_name: str) -> list[TfNSWSnapshot]:
        return self._parse_snapshot_list(self._read_fixture_json(fixture_name))

    def _load_fixture_raw(self, fixture_name: str) -> list[dict]:
        data = self._read_fixture_json(fixture_name)
        return data if isinstance(data, list) else [data]

    def _read_fixture_json(self, fixture_name: str) -> dict | list:
        path = self._settings.fixtures_dir / f"{fixture_name}.json"
        if not path.exists():
            raise FileNotFoundError(f"No fixture at {path}")
        return json.loads(path.read_text())
