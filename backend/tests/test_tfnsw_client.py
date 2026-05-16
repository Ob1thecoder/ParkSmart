import json
import pytest
import httpx
from datetime import date
from pathlib import Path
from unittest.mock import patch, MagicMock
from app.data.tfnsw_client import TfNSWClient, TfNSWSnapshot
from app.config import Settings

FIXTURES = Path(__file__).parent.parent / "data_raw/tfnsw_fixtures"


def _make_settings(tmp_path: Path, api_key: str = "") -> Settings:
    fixtures_dir = tmp_path / "fixtures"
    fixtures_dir.mkdir()
    for f in FIXTURES.glob("*.json"):
        (fixtures_dir / f.name).write_text(f.read_text())
    return Settings(tfnsw_api_key=api_key, fixtures_dir=fixtures_dir)


@pytest.fixture
def settings_no_key(tmp_path):
    return _make_settings(tmp_path)


@pytest.fixture
def settings_with_key(tmp_path):
    return _make_settings(tmp_path, api_key="test_key")


# --- get_occupancy ---

def test_get_occupancy_loads_fixture_when_no_key(settings_no_key):
    with TfNSWClient(settings_no_key) as client:
        result = client.get_occupancy("2060", fixture_name="chatswood_interchange")
    assert isinstance(result, TfNSWSnapshot)
    assert result.facility_id == "2060"
    assert result.available >= 0
    assert result.total_spots > 0


def test_get_occupancy_available_plus_occupied_equals_total(settings_no_key):
    with TfNSWClient(settings_no_key) as client:
        snap = client.get_occupancy("2060", fixture_name="chatswood_interchange")
    assert snap.available + snap.occupied == snap.total_spots


def test_get_occupancy_raises_when_fixture_missing(settings_no_key):
    with TfNSWClient(settings_no_key) as client:
        with pytest.raises(FileNotFoundError):
            client.get_occupancy("9999", fixture_name="nonexistent")


def test_get_occupancy_calls_api_when_key_present(settings_with_key):
    fixture_data = json.loads((FIXTURES / "chatswood_interchange.json").read_text())
    with TfNSWClient(settings_with_key) as client:
        with patch.object(client._http, "get") as mock_get:
            mock_resp = MagicMock()
            mock_resp.raise_for_status = MagicMock()
            mock_resp.json.return_value = fixture_data
            mock_get.return_value = mock_resp
            result = client.get_occupancy("2060", fixture_name="chatswood_interchange")
        mock_get.assert_called_once_with(
            "https://api.transport.nsw.gov.au/v1/carpark",
            params={"facility": "2060"}
        )
    assert isinstance(result, TfNSWSnapshot)


def test_get_occupancy_falls_back_to_fixture_on_http_error(settings_with_key):
    with TfNSWClient(settings_with_key) as client:
        with patch.object(client._http, "get") as mock_get:
            mock_resp = MagicMock()
            mock_resp.raise_for_status.side_effect = httpx.HTTPStatusError(
                "500", request=MagicMock(), response=MagicMock()
            )
            mock_get.return_value = mock_resp
            result = client.get_occupancy("2060", fixture_name="chatswood_interchange")
    assert isinstance(result, TfNSWSnapshot)
    assert result.total_spots > 0


# --- get_full_list ---

def test_get_full_list_returns_list_of_snapshots(settings_no_key):
    with TfNSWClient(settings_no_key) as client:
        result = client.get_full_list(fixture_name="full_list")
    assert isinstance(result, list)
    assert len(result) >= 1
    assert all(isinstance(s, TfNSWSnapshot) for s in result)


def test_get_full_list_each_snapshot_is_valid(settings_no_key):
    with TfNSWClient(settings_no_key) as client:
        snapshots = client.get_full_list(fixture_name="full_list")
    for snap in snapshots:
        assert snap.total_spots > 0
        assert snap.available + snap.occupied == snap.total_spots


# --- get_facility_list ---

def test_get_facility_list_returns_list(settings_no_key):
    with TfNSWClient(settings_no_key) as client:
        result = client.get_facility_list(fixture_name="facility_list")
    assert isinstance(result, list)
    assert len(result) >= 1


def test_get_facility_list_entries_have_id_and_name(settings_no_key):
    with TfNSWClient(settings_no_key) as client:
        result = client.get_facility_list(fixture_name="facility_list")
    for entry in result:
        assert "facility_id" in entry
        assert "facility_name" in entry


# --- get_history ---

def test_get_history_returns_list_of_snapshots(settings_no_key):
    with TfNSWClient(settings_no_key) as client:
        result = client.get_history(
            "2060", date(2026, 5, 10), fixture_name="history_sample"
        )
    assert isinstance(result, list)
    assert len(result) >= 1
    assert all(isinstance(s, TfNSWSnapshot) for s in result)


def test_get_history_snapshots_have_timestamps(settings_no_key):
    with TfNSWClient(settings_no_key) as client:
        result = client.get_history(
            "2060", date(2026, 5, 10), fixture_name="history_sample"
        )
    for snap in result:
        assert snap.ts is not None


def test_get_history_raises_when_fixture_missing(settings_no_key):
    with TfNSWClient(settings_no_key) as client:
        with pytest.raises(FileNotFoundError):
            client.get_history("2060", date(2099, 1, 1))
