import json
import pytest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from fastapi.testclient import TestClient
from app.config import Settings, get_settings
from app.main import app
from app.services.occupancy_service import backfill_sim_history


@pytest.fixture
def test_settings(seeded_db: Path) -> Settings:
    return Settings(
        db_path=seeded_db,
        tfnsw_api_key="",
        anthropic_api_key="test",
        fixtures_dir=Path("data_raw/tfnsw_fixtures"),
    )


@pytest.fixture
def client(test_settings: Settings):
    app.dependency_overrides[get_settings] = lambda: test_settings
    yield TestClient(app, raise_server_exceptions=True)
    app.dependency_overrides.clear()


# --- health ---

def test_health(client):
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


# --- /api/occupancy ---

def test_occupancy_returns_list(client):
    resp = client.get("/api/occupancy")
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)
    assert len(data) == 7


def test_occupancy_response_shape(client):
    resp = client.get("/api/occupancy")
    for item in resp.json():
        assert "car_park_id" in item
        assert "occupancy_pct" in item
        assert "lat" in item
        assert "lon" in item
        assert item["source"] in ("tfnsw", "simulated")


# --- /api/zones ---

def test_zones_victoria_avenue(client):
    resp = client.get("/api/zones", params={"street": "Victoria Avenue"})
    assert resp.status_code == 200
    data = resp.json()
    assert "street" in data
    assert len(data["segments"]) >= 1


def test_zones_not_found(client):
    resp = client.get("/api/zones", params={"street": "Imaginary Boulevard"})
    assert resp.status_code == 404


# --- /api/predict ---

def test_predict_returns_result(client):
    target = (datetime.now(timezone.utc) + timedelta(hours=5)).isoformat()
    resp = client.get("/api/predict", params={"location": "Westfield", "target_datetime": target})
    assert resp.status_code == 200
    data = resp.json()
    assert "predicted_occupancy_pct" in data
    assert "model_version" in data


def test_predict_out_of_range(client):
    target = (datetime.now(timezone.utc) + timedelta(days=10)).isoformat()
    resp = client.get("/api/predict", params={"location": "Westfield", "target_datetime": target})
    assert resp.status_code == 422


def test_predict_unknown_location(client):
    target = (datetime.now(timezone.utc) + timedelta(hours=2)).isoformat()
    resp = client.get("/api/predict", params={"location": "NotARealPlace XYZ", "target_datetime": target})
    assert resp.status_code == 404
