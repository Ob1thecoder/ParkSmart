import pytest
from pathlib import Path
from app.data.kml_loader import parse_kml, _parse_fields
from app.models import ParkingSignRecord, SignEntry

# Matches real Willoughby KML CDATA format
SAMPLE_KML = """\
<?xml version="1.0" encoding="UTF-8"?>
<kml xmlns="http://www.opengis.net/kml/2.2">
  <Document>
    <Placemark>
      <name>Sign 1</name>
      <description><![CDATA[Unknown Point Feature<BR><BR>
<B>id</B> = test-id-1<BR><BR>
<B>rawSignId</B> = 206927<BR><BR>
<B>signsPhotoURL</B> = https://example.com/sign1.jpg<BR><BR>
<B>sign1_category</B> = No Stopping<BR><BR>
<B>sign1_direction</B> = both<BR><BR>
<B>sign1_description</B> = At all times<BR><BR>
<B>sign2_category</B> = Restricted Parking<BR><BR>
<B>sign2_direction</B> = left<BR><BR>
<B>sign2_description</B> = Max Dur. 1 hour 8:30a - 6:00p M-F]]></description>
      <Point>
        <coordinates>151.18100,-33.79700,0</coordinates>
      </Point>
    </Placemark>
    <Placemark>
      <name>Sign 2</name>
      <description><![CDATA[Unknown Point Feature<BR><BR>
<B>id</B> = test-id-2<BR><BR>
<B>rawSignId</B> = 206928<BR><BR>
<B>sign1_category</B> = No Parking<BR><BR>
<B>sign1_direction</B> = right<BR><BR>
<B>sign1_description</B> = 8:30a - 6:00p Mon-Fri]]></description>
      <Point>
        <coordinates>151.18200,-33.79800,0</coordinates>
      </Point>
    </Placemark>
  </Document>
</kml>
"""

NO_POINT_KML = """\
<?xml version="1.0" encoding="UTF-8"?>
<kml xmlns="http://www.opengis.net/kml/2.2">
  <Document>
    <Placemark>
      <name>No point</name>
      <description><![CDATA[<B>sign1_category</B> = No Stopping]]></description>
    </Placemark>
  </Document>
</kml>
"""


@pytest.fixture
def kml_file(tmp_path: Path) -> Path:
    path = tmp_path / "test.kml"
    path.write_text(SAMPLE_KML)
    return path


def test_parse_kml_returns_list(kml_file):
    result = parse_kml(kml_file, geocode=False)
    assert isinstance(result, list)
    assert len(result) == 2


def test_parse_kml_returns_sign_records(kml_file):
    result = parse_kml(kml_file, geocode=False)
    for sign in result:
        assert isinstance(sign, ParkingSignRecord)


def test_parse_kml_coordinates(kml_file):
    result = parse_kml(kml_file, geocode=False)
    assert abs(result[0].lat - (-33.797)) < 0.001
    assert abs(result[0].lon - 151.181) < 0.001


def test_parse_kml_raw_description_preserved(kml_file):
    result = parse_kml(kml_file, geocode=False)
    assert "206927" in result[0].raw_description


def test_parse_kml_raw_sign_id(kml_file):
    result = parse_kml(kml_file, geocode=False)
    assert result[0].raw_sign_id == "206927"


def test_parse_kml_sign_photo_url(kml_file):
    result = parse_kml(kml_file, geocode=False)
    assert result[0].sign_photo_url == "https://example.com/sign1.jpg"


def test_parse_kml_sign_photo_url_none_when_absent(kml_file):
    result = parse_kml(kml_file, geocode=False)
    assert result[1].sign_photo_url is None


def test_parse_kml_signs_list(kml_file):
    result = parse_kml(kml_file, geocode=False)
    signs = result[0].signs
    assert len(signs) == 2
    assert all(isinstance(s, SignEntry) for s in signs)


def test_parse_kml_sign_fields(kml_file):
    result = parse_kml(kml_file, geocode=False)
    first = result[0].signs[0]
    assert first.category == "No Stopping"
    assert first.direction == "both"
    assert first.description == "At all times"


def test_parse_kml_second_sign(kml_file):
    result = parse_kml(kml_file, geocode=False)
    second = result[0].signs[1]
    assert second.category == "Restricted Parking"
    assert second.direction == "left"


def test_parse_kml_skips_placemarks_without_point(tmp_path):
    path = tmp_path / "nopoint.kml"
    path.write_text(NO_POINT_KML)
    result = parse_kml(path, geocode=False)
    assert result == []


def test_parse_fields_extracts_key_value_pairs():
    html = "<B>sign1_category</B> = No Stopping<BR><B>sign1_direction</B> = both"
    fields = _parse_fields(html)
    assert fields["sign1_category"] == "No Stopping"
    assert fields["sign1_direction"] == "both"


def test_parse_fields_ignores_empty_values():
    html = "<B>rawSignId</B> = 12345<BR><B>signsPhotoURL</B> = "
    fields = _parse_fields(html)
    assert fields.get("rawSignId") == "12345"
    assert "signsPhotoURL" not in fields


def test_parse_kml_geocode_failure_does_not_crash(tmp_path):
    from unittest.mock import patch
    path = tmp_path / "test.kml"
    path.write_text(SAMPLE_KML)
    with patch("app.data.kml_loader._geocode_one", return_value=None):
        result = parse_kml(path, geocode=True)
    assert len(result) == 2
    for sign in result:
        assert sign.street is None


def test_parse_kml_uses_geocode_cache(tmp_path, monkeypatch):
    import json
    kml = tmp_path / "test.kml"
    kml.write_text(SAMPLE_KML)
    cache = tmp_path / "geocode_cache.json"
    cache.write_text(json.dumps({
        "-33.797,151.181": "Victoria Avenue",
        "-33.798,151.182": "Albert Avenue",
    }))

    def _boom(*args, **kwargs):
        raise AssertionError("_geocode_one called despite a full cache")

    monkeypatch.setattr("app.data.kml_loader._geocode_one", _boom)

    result = parse_kml(kml, geocode=True, cache_path=cache)
    assert result[0].street == "Victoria Avenue"
    assert result[1].street == "Albert Avenue"


def test_parse_kml_writes_geocode_cache(tmp_path, monkeypatch):
    import json
    kml = tmp_path / "test.kml"
    kml.write_text(SAMPLE_KML)
    cache = tmp_path / "geocode_cache.json"

    monkeypatch.setattr(
        "app.data.kml_loader._geocode_one", lambda client, lat, lon: f"Road {lat}"
    )
    monkeypatch.setattr("app.data.kml_loader.time.sleep", lambda s: None)

    parse_kml(kml, geocode=True, cache_path=cache)
    assert cache.exists()
    saved = json.loads(cache.read_text())
    assert saved["-33.797,151.181"] == "Road -33.797"
    assert saved["-33.798,151.182"] == "Road -33.798"


def test_parse_kml_does_not_cache_failed_geocode(tmp_path, monkeypatch):
    import json
    kml = tmp_path / "test.kml"
    kml.write_text(SAMPLE_KML)
    cache = tmp_path / "geocode_cache.json"

    monkeypatch.setattr("app.data.kml_loader._geocode_one", lambda client, lat, lon: None)
    monkeypatch.setattr("app.data.kml_loader.time.sleep", lambda s: None)

    parse_kml(kml, geocode=True, cache_path=cache)
    # No successful lookups → nothing written, so failures retry next run.
    assert not cache.exists()
