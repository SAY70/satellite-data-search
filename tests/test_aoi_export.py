"""Tests for AOI export/import round-tripping.

These use GeoJSON-style dicts rather than ee.Geometry so they run without
an Earth Engine session.
"""

import json

import pytest

import aoi_export

SQUARE = [[[-88.9, 33.4], [-88.7, 33.4], [-88.7, 33.5], [-88.9, 33.5], [-88.9, 33.4]]]


class TestToCoordinates:
    def test_accepts_plain_geometry_dict(self):
        out = aoi_export._to_coordinates({"type": "Polygon", "coordinates": SQUARE})
        assert out == SQUARE

    def test_accepts_feature_wrapper(self):
        feature = {"geometry": {"type": "Polygon", "coordinates": SQUARE}}
        assert aoi_export._to_coordinates(feature) == SQUARE

    def test_rejects_non_polygon_with_helpful_message(self):
        """Drawing a marker instead of a polygon is an easy mistake to make."""
        with pytest.raises(ValueError, match="Polygon"):
            aoi_export._to_coordinates({"type": "Point", "coordinates": [-88.8, 33.4]})

    def test_rejects_wrong_type(self):
        with pytest.raises(TypeError):
            aoi_export._to_coordinates("not a geometry")


class TestExportGeoJSON:
    def test_writes_valid_feature_collection(self, tmp_path):
        out = aoi_export.export_geojson(
            {"type": "Polygon", "coordinates": SQUARE}, tmp_path / "aoi.geojson", name="test_aoi"
        )
        data = json.loads(out.read_text())

        assert data["type"] == "FeatureCollection"
        assert len(data["features"]) == 1
        assert data["features"][0]["geometry"]["coordinates"] == SQUARE
        assert data["features"][0]["properties"]["name"] == "test_aoi"

    def test_creates_missing_parent_directory(self, tmp_path):
        target = tmp_path / "nested" / "deeper" / "aoi.geojson"
        aoi_export.export_geojson({"type": "Polygon", "coordinates": SQUARE}, target)
        assert target.exists()

    def test_round_trips_coordinates_unchanged(self, tmp_path):
        """The search step reads this back; any coordinate mangling breaks everything."""
        out = aoi_export.export_geojson({"type": "Polygon", "coordinates": SQUARE}, tmp_path / "a.geojson")
        reloaded = json.loads(out.read_text())["features"][0]["geometry"]["coordinates"]
        assert reloaded == SQUARE


class TestExportKmlKmz:
    def test_kml_is_written_and_non_empty(self, tmp_path):
        out = aoi_export.export_kml({"type": "Polygon", "coordinates": SQUARE}, tmp_path / "aoi.kml")
        text = out.read_text(encoding="utf-8")
        assert out.stat().st_size > 0
        assert "<kml" in text.lower()

    def test_kmz_is_written_and_is_a_zip(self, tmp_path):
        out = aoi_export.export_kmz({"type": "Polygon", "coordinates": SQUARE}, tmp_path / "aoi.kmz")
        assert out.stat().st_size > 0
        assert out.read_bytes()[:2] == b"PK"  # zip magic number


def test_export_all_writes_all_three_formats(tmp_path):
    paths = aoi_export.export_all({"type": "Polygon", "coordinates": SQUARE}, tmp_path, name="my_aoi")

    assert set(paths) == {"geojson", "kml", "kmz"}
    for fmt, path in paths.items():
        assert path.exists(), f"{fmt} not written"
        assert path.stat().st_size > 0, f"{fmt} is empty"
        assert path.stem == "my_aoi"
