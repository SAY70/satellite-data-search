"""Live orbit tracking: current positions and physics-based overpass forecast
from real-time TLEs (CelesTrak) propagated with skyfield. No Earth Engine or
login needed. Shared by the live-tracker notebook and the dashboard app.
"""

import math

import numpy as np
import pandas as pd
import requests
from skyfield.api import EarthSatellite, load, wgs84

SWATH_HALF_WIDTH_KM = {
    "SENTINEL-1A": 125, "SENTINEL-1C": 125,
    "SENTINEL-2A": 145, "SENTINEL-2B": 145, "SENTINEL-2C": 145,
    "LANDSAT 8": 92, "LANDSAT 9": 92,
}

PLATFORM_COLORS = {
    "SENTINEL-1A": "#14b8a6", "SENTINEL-1C": "#0f766e",
    "SENTINEL-2A": "#eab308", "SENTINEL-2B": "#facc15", "SENTINEL-2C": "#fde047",
    "LANDSAT 8": "#f97316", "LANDSAT 9": "#c2410c",
}


def _haversine_km(lat1, lon1, lat2, lon2):
    r = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dlambda / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def _haversine_km_vec(lat1, lon1, lat2, lon2):
    r = 6371.0
    p1, p2 = np.radians(lat1), np.radians(lat2)
    dphi = np.radians(lat2 - lat1)
    dlambda = np.radians(lon2 - lon1)
    a = np.sin(dphi / 2) ** 2 + np.cos(p1) * np.cos(p2) * np.sin(dlambda / 2) ** 2
    return 2 * r * np.arcsin(np.sqrt(a))


def load_tles(names=None):
    """Fetches current TLEs from CelesTrak. Returns (timescale, {name: EarthSatellite})."""
    names = names or list(SWATH_HALF_WIDTH_KM)
    ts = load.timescale()
    satellites = {}
    for name in names:
        resp = requests.get(
            "https://celestrak.org/NORAD/elements/gp.php", params={"NAME": name, "FORMAT": "TLE"}, timeout=30
        )
        lines = [l for l in resp.text.strip().split("\n") if l.strip()]
        if len(lines) < 3:
            continue
        satellites[name] = EarthSatellite(lines[1], lines[2], lines[0], ts)
    return ts, satellites


def snapshot(satellites, ts, aoi_lat, aoi_lon):
    """Current lat/lon/altitude/distance-from-AOI for every tracked satellite."""
    t_now = ts.now()
    rows = []
    for name, sat in satellites.items():
        subpoint = wgs84.subpoint(sat.at(t_now))
        lat, lon = subpoint.latitude.degrees, subpoint.longitude.degrees
        rows.append(
            {
                "satellite": name,
                "lat": lat,
                "lon": lon,
                "altitude_km": subpoint.elevation.km,
                "distance_from_aoi_km": _haversine_km(lat, lon, aoi_lat, aoi_lon),
            }
        )
    return t_now, pd.DataFrame(rows).sort_values("distance_from_aoi_km").reset_index(drop=True)


def ground_track(sat, ts, t_now, minutes_before=20, minutes_after=100, step_seconds=30):
    """Returns a list of (lat, lon) polyline segments (split at the antimeridian)."""
    offsets_min = [m / 60 for m in range(-minutes_before * 60, minutes_after * 60, step_seconds)]
    times = ts.tt_jd(t_now.tt + [m / 1440 for m in offsets_min])
    subpoints = wgs84.subpoint(sat.at(times))
    lats, lons = subpoints.latitude.degrees, subpoints.longitude.degrees

    segments = []
    segment = [(lats[0], lons[0])]
    for i in range(1, len(lats)):
        if abs(lons[i] - lons[i - 1]) > 180:
            segments.append(segment)
            segment = []
        segment.append((lats[i], lons[i]))
    segments.append(segment)
    return segments


def orbital_forecast(satellites, ts, t_now, aoi_lat, aoi_lon, forecast_days=30, step_seconds=30):
    """Finds every time each satellite's ground track passes within swath range of the AOI."""
    n_samples = int(forecast_days * 86400 / step_seconds)
    offsets_days = np.arange(n_samples) * step_seconds / 86400.0
    forecast_times = ts.tt_jd(t_now.tt + offsets_days)

    rows = []
    for name, sat in satellites.items():
        half_width = SWATH_HALF_WIDTH_KM[name]
        subpoints = wgs84.subpoint(sat.at(forecast_times))
        lats, lons = subpoints.latitude.degrees, subpoints.longitude.degrees
        dist = _haversine_km_vec(lats, lons, aoi_lat, aoi_lon)

        is_min = (dist[1:-1] < dist[:-2]) & (dist[1:-1] < dist[2:]) & (dist[1:-1] < half_width)
        idx = np.where(is_min)[0] + 1

        for i in idx:
            predicted_dt = forecast_times[i].utc_datetime()
            rows.append(
                {
                    "satellite": name,
                    "predicted_datetime_utc": predicted_dt.replace(tzinfo=None),
                    "days_until": offsets_days[i],
                    "closest_approach_km": dist[i],
                    "swath_half_width_km": half_width,
                }
            )

    return pd.DataFrame(rows).sort_values("predicted_datetime_utc").reset_index(drop=True)
