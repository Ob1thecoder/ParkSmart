import json
import logging
from collections import defaultdict
from pathlib import Path

from app.db import get_connection
from app.models import RestrictionRule, ZoneResponse, ZoneSegment

log = logging.getLogger(__name__)

_SEED_PATH = Path(__file__).parent.parent / "data" / "seed_zones.json"
_seed_cache: dict | None = None


def _load_seed() -> dict:
    global _seed_cache
    if _seed_cache is None:
        _seed_cache = json.loads(_SEED_PATH.read_text())
    return _seed_cache


def get_zone_restrictions(street: str, db_path: Path) -> dict:
    """LLM tool 3: get_zone_restrictions. Returns ZoneResponse dict or {"error": "not_found"}."""
    # 1. Try DB (KML-sourced signs geocoded to this street)
    normalized = street.strip()
    with get_connection(db_path) as con:
        rows = con.execute(
            "SELECT sign_categories, sign_photo_url FROM parking_signs "
            "WHERE LOWER(street) = LOWER(?)",
            (normalized,),
        ).fetchall()

    if rows:
        segments = _signs_to_segments([dict(r) for r in rows])
        return ZoneResponse(street=normalized, segments=segments).model_dump()

    # 2. Fall back to seed_zones.json (keyed by normalized lowercase street name)
    seed = _load_seed()
    seed_key = normalized.lower().replace(" ", "_")
    if seed_key in seed:
        entry = seed[seed_key]
        segments = [
            ZoneSegment(
                side=seg.get("side"),
                rules_plain_english=seg["rules_plain_english"],
                rules_structured=[RestrictionRule(**r) for r in seg.get("rules_structured", [])],
                sign_photo_url=seg.get("sign_photo_url"),
            )
            for seg in entry["segments"]
        ]
        return ZoneResponse(street=entry["street"], segments=segments).model_dump()

    return {"error": "not_found"}


def _signs_to_segments(rows: list[dict]) -> list[ZoneSegment]:
    """Group DB sign rows into segments by direction."""
    groups: dict[str | None, list[dict]] = defaultdict(list)
    photo_by_side: dict[str | None, str | None] = {}

    for row in rows:
        entries = json.loads(row["sign_categories"])
        photo_url = row.get("sign_photo_url")
        for entry in entries:
            direction = entry.get("direction", "none")
            side: str | None = direction if direction in ("left", "right") else None
            groups[side].append(entry)
            if photo_url and side not in photo_by_side:
                photo_by_side[side] = photo_url

    segments = []
    for side, entries in groups.items():
        plain = ". ".join(
            f"{e['category']}: {e['description']}" for e in entries if e.get("description")
        )
        if not plain:
            plain = ". ".join(e["category"] for e in entries)
        segments.append(
            ZoneSegment(
                side=side,
                rules_plain_english=plain,
                rules_structured=[],
                sign_photo_url=photo_by_side.get(side),
            )
        )
    return segments
