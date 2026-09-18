"""Tests for search-result parsing and filtering.

The CMR footprint parser is the highest-risk piece here: CMR returns
"lat lon lat lon ..." but GeoJSON wants (lon, lat), and getting that
backwards puts every scene footprint in the wrong hemisphere.
"""

import numpy as np
import pandas as pd
import pytest

import sat_search


class TestSensorFromProduct:
    @pytest.mark.parametrize("label,expected", [
        ("Sentinel-1 GRD High-Res (Dual-pol)", "Sentinel-1"),
        ("Sentinel-2 L2A (Surface Reflectance)", "Sentinel-2"),
        ("Landsat 8 C2 L2 (Surface Reflectance)", "Landsat"),
        ("Landsat HLS L30", "Landsat"),
        ("NISAR L2 GCOV (Geocoded Covariance)", "NISAR"),
        ("MODIS Terra Snow Cover", "MODIS"),
        ("Sentinel-6 Low-Res OST (NTC)", "Sentinel-6"),
    ])
    def test_extracts_sensor(self, label, expected):
        assert sat_search._sensor_from_product(label) == expected

    def test_every_configured_product_yields_a_known_sensor(self):
        """Guards against adding a product whose label doesn't map to its sensor."""
        for sensor, (ee_products, cmr_products) in sat_search.SENSOR_PRODUCTS.items():
            for label in list(ee_products) + list(cmr_products):
                assert sat_search._sensor_from_product(label) == sensor, (
                    f"{label!r} is registered under {sensor!r} but parses as "
                    f"{sat_search._sensor_from_product(label)!r}"
                )


class TestGranuleFootprint:
    def test_swaps_lat_lon_to_lon_lat(self):
        """CMR gives 'lat lon ...'; GeoJSON needs [lon, lat]."""
        granule = {"polygons": [["33.0 -88.0 33.0 -89.0 34.0 -89.0 33.0 -88.0"]]}
        out = sat_search._granule_footprint(granule)

        assert out["type"] == "Polygon"
        assert out["coordinates"][0] == [
            [-88.0, 33.0], [-89.0, 33.0], [-89.0, 34.0], [-88.0, 33.0]
        ]

    def test_longitudes_are_negative_in_western_hemisphere(self):
        """A sanity check that would fail loudly if the swap regressed."""
        granule = {"polygons": [["33.4 -88.8 33.5 -88.7 33.4 -88.8"]]}
        coords = sat_search._granule_footprint(granule)["coordinates"][0]
        lons = [c[0] for c in coords]
        lats = [c[1] for c in coords]
        assert all(l < -80 for l in lons), "longitude should be ~-88, got {lons}"
        assert all(30 < l < 40 for l in lats), f"latitude should be ~33, got {lats}"

    def test_missing_polygons_returns_none(self):
        assert sat_search._granule_footprint({}) is None
        assert sat_search._granule_footprint({"polygons": None}) is None


class TestGranuleLink:
    def test_prefers_zip_over_other_data_links(self):
        granule = {"links": [
            {"rel": "http://esipfed.org/ns/fedsearch/1.1/data#", "href": "https://x/scene.tif"},
            {"rel": "http://esipfed.org/ns/fedsearch/1.1/data#", "href": "https://x/scene.zip"},
        ]}
        assert sat_search._granule_link(granule).endswith(".zip")

    def test_falls_back_to_first_data_link(self):
        granule = {"links": [
            {"rel": "http://esipfed.org/ns/fedsearch/1.1/data#", "href": "https://x/scene.tif"},
        ]}
        assert sat_search._granule_link(granule) == "https://x/scene.tif"

    def test_ignores_non_data_links(self):
        """Browse/metadata links must not be mistaken for the download."""
        granule = {"links": [
            {"rel": "http://esipfed.org/ns/fedsearch/1.1/browse#", "href": "https://x/thumb.png"},
        ]}
        assert sat_search._granule_link(granule) is None

    def test_no_links_returns_none(self):
        assert sat_search._granule_link({}) is None


class TestFilterScenes:
    @staticmethod
    def _df(rows):
        return pd.DataFrame(rows)

    def test_drops_low_coverage(self):
        df = self._df([
            {"id": "a", "aoi_cov_pct": 100.0, "cloud_pct": 5.0},
            {"id": "b", "aoi_cov_pct": 12.0, "cloud_pct": 5.0},
        ])
        out = sat_search.filter_scenes(df, min_aoi_cov_pct=50, max_cloud_pct=30)
        assert list(out["id"]) == ["a"]

    def test_drops_cloudy_optical(self):
        df = self._df([
            {"id": "a", "aoi_cov_pct": 100.0, "cloud_pct": 5.0},
            {"id": "b", "aoi_cov_pct": 100.0, "cloud_pct": 90.0},
        ])
        out = sat_search.filter_scenes(df, min_aoi_cov_pct=50, max_cloud_pct=30)
        assert list(out["id"]) == ["a"]

    def test_keeps_radar_rows_with_no_cloud_value(self):
        """SAR has no cloud_pct; it must not be filtered out as if it were 0% or 100%."""
        df = self._df([
            {"id": "sar", "aoi_cov_pct": 100.0, "cloud_pct": np.nan},
            {"id": "optical", "aoi_cov_pct": 100.0, "cloud_pct": 90.0},
        ])
        out = sat_search.filter_scenes(df, min_aoi_cov_pct=50, max_cloud_pct=30)
        assert list(out["id"]) == ["sar"]

    def test_handles_frame_with_no_cloud_column(self):
        """An all-radar search has no cloud_pct column at all."""
        df = self._df([{"id": "sar", "aoi_cov_pct": 100.0}])
        out = sat_search.filter_scenes(df, min_aoi_cov_pct=50, max_cloud_pct=30)
        assert list(out["id"]) == ["sar"]

    def test_empty_input_returns_empty(self):
        assert sat_search.filter_scenes(pd.DataFrame()).empty


class TestTidy:
    def test_puts_key_columns_first(self):
        df = pd.DataFrame([{"link": "x", "id": "a", "date": "2026-01-01", "product": "P", "sensor": "S"}])
        out = sat_search._tidy(df)
        assert list(out.columns)[:4] == ["product", "sensor", "id", "date"]

    def test_empty_frame_passes_through(self):
        assert sat_search._tidy(pd.DataFrame()).empty


def test_every_sensor_has_a_colour():
    """A sensor with no colour silently vanishes from the map legend."""
    missing = set(sat_search.SENSOR_PRODUCTS) - set(sat_search.SENSOR_COLORS)
    assert not missing, f"sensors with no map colour: {missing}"


def test_cmr_products_declare_required_fields():
    """search_cmr_products indexes these directly, so a typo fails at runtime."""
    for sensor, (_, cmr_products) in sat_search.SENSOR_PRODUCTS.items():
        for label, cfg in cmr_products.items():
            assert "provider" in cfg, f"{label} missing provider"
            assert cfg.get("short_names"), f"{label} missing short_names"
            assert "id_regex" in cfg, f"{label} missing id_regex (use None if not needed)"


def test_ee_products_declare_required_fields():
    for sensor, (ee_products, _) in sat_search.SENSOR_PRODUCTS.items():
        for label, cfg in ee_products.items():
            assert cfg.get("collection_id"), f"{label} missing collection_id"
            assert "properties" in cfg, f"{label} missing properties map"
