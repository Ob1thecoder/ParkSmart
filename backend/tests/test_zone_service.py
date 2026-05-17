import json
import pytest
from pathlib import Path
from app.config import Settings
from app.db import get_connection
from app.services import zone_service


# --- get_zone_restrictions ---

def test_victoria_avenue_returns_from_seed(seeded_db):
    result = zone_service.get_zone_restrictions("Victoria Avenue", seeded_db)
    assert "error" not in result
    assert result["street"].lower() == "victoria avenue"
    assert len(result["segments"]) >= 1


def test_zone_not_found(seeded_db):
    result = zone_service.get_zone_restrictions("Nonexistent Boulevard", seeded_db)
    assert result == {"error": "not_found"}


def test_victoria_avenue_case_insensitive(seeded_db):
    result = zone_service.get_zone_restrictions("victoria avenue", seeded_db)
    assert "error" not in result


def test_zone_segments_have_required_fields(seeded_db):
    result = zone_service.get_zone_restrictions("Victoria Avenue", seeded_db)
    for seg in result["segments"]:
        assert "rules_plain_english" in seg
        assert "rules_structured" in seg
        assert isinstance(seg["rules_structured"], list)


def test_zone_from_db_when_signs_loaded(seeded_db):
    # Insert two fake signs for "Albert Avenue" into the DB
    sign_cats = json.dumps([
        {"category": "No Stopping", "direction": "both", "description": "At all times"}
    ])
    with get_connection(seeded_db) as con:
        con.execute(
            "INSERT INTO parking_signs (lat, lon, street, raw_description, sign_categories) "
            "VALUES (-33.798, 151.183, 'Albert Avenue', 'raw', ?)",
            (sign_cats,),
        )
    result = zone_service.get_zone_restrictions("Albert Avenue", seeded_db)
    assert "error" not in result
    assert result["street"] == "Albert Avenue"
    assert len(result["segments"]) == 1
    assert "No Stopping" in result["segments"][0]["rules_plain_english"]


def test_signs_to_segments_groups_by_direction(seeded_db):
    sign_cats = json.dumps([
        {"category": "No Stopping", "direction": "left", "description": "7am-10am"},
        {"category": "Restricted Parking", "direction": "right", "description": "2P 10am-6pm"},
    ])
    with get_connection(seeded_db) as con:
        con.execute(
            "INSERT INTO parking_signs (lat, lon, street, raw_description, sign_categories) "
            "VALUES (-33.798, 151.183, 'Test Street', 'raw', ?)",
            (sign_cats,),
        )
    result = zone_service.get_zone_restrictions("Test Street", seeded_db)
    sides = {seg["side"] for seg in result["segments"]}
    assert "left" in sides
    assert "right" in sides


def test_list_streets_includes_seed_and_sorted(seeded_db):
    streets = zone_service.list_streets(seeded_db)
    assert "Victoria Avenue" in streets
    assert streets == sorted(streets, key=str.casefold)
