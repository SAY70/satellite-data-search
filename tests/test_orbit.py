"""Tests for the orbit-tracking geometry helpers.

The scalar and vectorised haversine implementations are separate code paths
(one used for the position snapshot, one for the 30-day forecast sweep), so
they're checked against each other as well as against known distances.
"""

import numpy as np
import pytest

import sat_orbit


class TestHaversine:
    def test_zero_distance(self):
        assert sat_orbit._haversine_km(33.4, -88.8, 33.4, -88.8) == pytest.approx(0.0, abs=1e-9)

    def test_one_degree_of_longitude_at_equator(self):
        """~111.19 km for a 6371 km sphere."""
        assert sat_orbit._haversine_km(0, 0, 0, 1) == pytest.approx(111.19, abs=0.1)

    def test_one_degree_of_latitude(self):
        """Latitude degrees are ~constant length anywhere."""
        assert sat_orbit._haversine_km(0, 0, 1, 0) == pytest.approx(111.19, abs=0.1)

    def test_longitude_degrees_shrink_toward_the_pole(self):
        """At 60N a degree of longitude is about half its equatorial length."""
        equator = sat_orbit._haversine_km(0, 0, 0, 1)
        high_lat = sat_orbit._haversine_km(60, 0, 60, 1)
        assert high_lat == pytest.approx(equator / 2, rel=0.01)

    def test_is_symmetric(self):
        a = sat_orbit._haversine_km(33.4, -88.8, 40.0, -75.0)
        b = sat_orbit._haversine_km(40.0, -75.0, 33.4, -88.8)
        assert a == pytest.approx(b)

    def test_antipodal_is_half_circumference(self):
        half = np.pi * 6371.0
        assert sat_orbit._haversine_km(0, 0, 0, 180) == pytest.approx(half, rel=1e-6)


class TestHaversineVectorised:
    def test_matches_scalar_implementation(self):
        """The forecast sweep must agree with the snapshot calculation."""
        lats = np.array([0.0, 33.4, -45.0, 70.0])
        lons = np.array([0.0, -88.8, 120.0, -10.0])
        target_lat, target_lon = 33.47, -88.77

        vectorised = sat_orbit._haversine_km_vec(lats, lons, target_lat, target_lon)
        scalar = [sat_orbit._haversine_km(la, lo, target_lat, target_lon) for la, lo in zip(lats, lons)]

        np.testing.assert_allclose(vectorised, scalar, rtol=1e-9)

    def test_returns_array_of_matching_length(self):
        lats = np.linspace(-80, 80, 50)
        lons = np.linspace(-180, 180, 50)
        out = sat_orbit._haversine_km_vec(lats, lons, 0.0, 0.0)
        assert out.shape == (50,)
        assert np.all(out >= 0)


def test_every_tracked_satellite_has_a_swath_and_colour():
    """A satellite with no swath width can't be used for overpass detection."""
    assert set(sat_orbit.SWATH_HALF_WIDTH_KM) == set(sat_orbit.PLATFORM_COLORS)


def test_swath_half_widths_are_plausible():
    """Guards against entering a full swath width where a half-width is expected."""
    for name, half_width in sat_orbit.SWATH_HALF_WIDTH_KM.items():
        assert 10 < half_width < 400, f"{name}: {half_width} km is not a plausible half-swath"
