import re
import logging
import time
from pathlib import Path

import httpx
from lxml import etree

from app.models import ParkingSignRecord, SignEntry

log = logging.getLogger(__name__)

_KML_NS = "http://www.opengis.net/kml/2.2"
_FIELD_RE = re.compile(r"<B>([^<]+)</B>\s*=\s*([^<\n]+)")
_NOMINATIM_URL = "https://nominatim.openstreetmap.org/reverse"
_USER_AGENT = "ParkSmart/1.0 (parking assistant for Chatswood CBD; contact duyminhle21@gmail.com)"


def parse_kml(kml_path: Path, *, geocode: bool = True) -> list[ParkingSignRecord]:
    tree = etree.parse(str(kml_path))
    root = tree.getroot()

    records: list[ParkingSignRecord] = []
    for placemark in root.iter(f"{{{_KML_NS}}}Placemark"):
        point = placemark.find(f".//{{{_KML_NS}}}Point")
        if point is None:
            continue
        coords_el = point.find(f"{{{_KML_NS}}}coordinates")
        if coords_el is None or not coords_el.text:
            continue

        lon_s, lat_s, *_ = coords_el.text.strip().split(",")
        lat, lon = float(lat_s), float(lon_s)

        desc_el = placemark.find(f".//{{{_KML_NS}}}description")
        raw = (desc_el.text or "").strip() if desc_el is not None else ""

        fields = _parse_fields(raw)

        raw_sign_id = fields.get("rawSignId")
        photo_url = fields.get("signsPhotoURL") or None

        signs: list[SignEntry] = []
        for n in range(1, 5):
            cat = fields.get(f"sign{n}_category")
            if not cat:
                continue
            signs.append(
                SignEntry(
                    category=cat,
                    direction=fields.get(f"sign{n}_direction", "none"),
                    description=fields.get(f"sign{n}_description", ""),
                )
            )

        records.append(
            ParkingSignRecord(
                raw_sign_id=raw_sign_id,
                lat=lat,
                lon=lon,
                street=None,
                raw_description=raw,
                signs=signs,
                sign_photo_url=photo_url,
            )
        )

    log.info("Parsed %d signs from %s", len(records), kml_path.name)

    if geocode and records:
        _reverse_geocode_all(records)

    return records


def _parse_fields(html: str) -> dict[str, str]:
    """Extract <B>key</B> = value pairs from CDATA HTML. Skips blank values."""
    result: dict[str, str] = {}
    for m in _FIELD_RE.finditer(html):
        key = m.group(1).strip()
        val = m.group(2).strip()
        if val:
            result[key] = val
    return result


def _reverse_geocode_all(records: list[ParkingSignRecord]) -> None:
    with httpx.Client(headers={"User-Agent": _USER_AGENT}, timeout=10.0) as client:
        for record in records:
            street = _geocode_one(client, record.lat, record.lon)
            record.street = street
            time.sleep(1.0)  # Nominatim rate limit: 1 req/s


def _geocode_one(client: httpx.Client, lat: float, lon: float) -> str | None:
    try:
        resp = client.get(
            _NOMINATIM_URL,
            params={"lat": lat, "lon": lon, "format": "json"},
        )
        resp.raise_for_status()
        address = resp.json().get("address", {})
        return (
            address.get("road")
            or address.get("pedestrian")
            or address.get("path")
        )
    except Exception:
        log.warning("Nominatim geocode failed for (%s, %s)", lat, lon)
        return None
