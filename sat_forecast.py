"""Empirical revisit-pattern overpass forecast: detects each platform's real
recent gap pattern (not the textbook nominal cycle) and projects it forward.
Shared by the forecast notebook and the dashboard app.
"""

from datetime import timedelta

import ee
import pandas as pd
import requests

NOMINAL_REPEAT_CYCLE_DAYS = {
    "Sentinel-2A": 10, "Sentinel-2B": 10, "Sentinel-2C": 10,
    "Sentinel-1A": 12, "Sentinel-1B": 12, "Sentinel-1C": 12,
    "LANDSAT_8": 16, "LANDSAT_9": 16,
    "NISAR": 12,
    "MODIS Terra": 1, "MODIS Aqua": 1,
}

PLATFORM_COLORS = {
    "Sentinel-2A": "#eab308", "Sentinel-2B": "#facc15", "Sentinel-2C": "#fde047",
    "Sentinel-1A": "#14b8a6", "Sentinel-1B": "#0d9488", "Sentinel-1C": "#0f766e",
    "LANDSAT_8": "#f97316", "LANDSAT_9": "#c2410c",
    "NISAR": "#a855f7",
    "MODIS Terra": "#0ea5e9", "MODIS Aqua": "#38bdf8",
}


def _detect_period(gaps, max_period=4):
    """Smallest period P such that the last P gaps match the P gaps before them (±1 day)."""
    for period in range(1, min(max_period, len(gaps) // 2) + 1):
        recent = gaps[-period:]
        prior = gaps[-2 * period : -period]
        if len(prior) == period and all(abs(a - b) <= 1 for a, b in zip(recent, prior)):
            return period
    return None


def _fetch_asf_history(bbox, history_start, history_end, short_names, platform_from_id, footprints, rows):
    resp = requests.get(
        "https://cmr.earthdata.nasa.gov/search/granules.json",
        params={
            "short_name": short_names,
            "provider": "ASF",
            "bounding_box": bbox,
            "temporal": f"{history_start}T00:00:00Z,{history_end}T00:00:00Z",
            "page_size": 200,
        },
        timeout=60,
    )
    entries = resp.json()["feed"]["entry"]
    for g in entries:
        granule_id = g.get("producer_granule_id", "")
        platform = platform_from_id(granule_id)
        if not platform:
            continue
        polygons = g.get("polygons")
        if polygons:
            ring = polygons[0][0].split()
            points = [[float(ring[i + 1]), float(ring[i])] for i in range(0, len(ring), 2)]
            footprints[(platform, granule_id)] = {"type": "Polygon", "coordinates": [points]}
        rows.append({"id": granule_id, "platform": platform, "time": g.get("time_start")})
    return len(entries)


def gather_history(geometry, history_start, history_end, progress_cb=None):
    """Pulls recent acquisitions for Sentinel-1/2, Landsat, NISAR, MODIS over the AOI.

    Returns (history_df, footprints). `progress_cb(label, count)` fires once
    per source queried.
    """
    footprints = {}
    rows = []

    s2_col = ee.ImageCollection("COPERNICUS/S2_SR_HARMONIZED").filterBounds(geometry).filterDate(history_start, history_end)

    def _s2_props(img):
        return ee.Feature(
            img.geometry(),
            {
                "id": img.get("system:index"),
                "platform": img.get("SPACECRAFT_NAME"),
                "time": img.date().format("YYYY-MM-dd'T'HH:mm:ss"),
            },
        )

    info = ee.FeatureCollection(s2_col.map(_s2_props)).getInfo()
    if progress_cb:
        progress_cb("Sentinel-2", len(info["features"]))
    for f in info["features"]:
        props = f["properties"]
        footprints[(props["platform"], props["id"])] = f["geometry"]
        rows.append(props)

    for collection_id in ["LANDSAT/LC08/C02/T1_L2", "LANDSAT/LC09/C02/T1_L2"]:
        col = ee.ImageCollection(collection_id).filterBounds(geometry).filterDate(history_start, history_end)

        def _ls_props(img):
            return ee.Feature(
                img.geometry(),
                {
                    "id": img.get("system:index"),
                    "platform": img.get("SPACECRAFT_ID"),
                    "time": img.date().format("YYYY-MM-dd'T'HH:mm:ss"),
                },
            )

        info = ee.FeatureCollection(col.map(_ls_props)).getInfo()
        if progress_cb:
            progress_cb(collection_id, len(info["features"]))
        for f in info["features"]:
            props = f["properties"]
            footprints[(props["platform"], props["id"])] = f["geometry"]
            rows.append(props)

    for collection_id, platform in [("MODIS/061/MOD10A1", "MODIS Terra"), ("MODIS/061/MYD10A1", "MODIS Aqua")]:
        col = ee.ImageCollection(collection_id).filterBounds(geometry).filterDate(history_start, history_end)

        def _modis_props(img):
            return ee.Feature(
                img.geometry(), {"id": img.get("system:index"), "time": img.date().format("YYYY-MM-dd'T'HH:mm:ss")}
            )

        info = ee.FeatureCollection(col.map(_modis_props)).getInfo()
        if progress_cb:
            progress_cb(platform, len(info["features"]))
        for f in info["features"]:
            props = f["properties"]
            props["platform"] = platform
            footprints[(platform, props["id"])] = f["geometry"]
            rows.append(props)

    coords = geometry.bounds(1).coordinates().getInfo()[0]
    lons = [c[0] for c in coords]
    lats = [c[1] for c in coords]
    bbox = f"{min(lons)},{min(lats)},{max(lons)},{max(lats)}"

    def _s1_platform(granule_id):
        return f"Sentinel-1{granule_id[2]}" if granule_id.startswith("S1") else None

    n = _fetch_asf_history(
        bbox, history_start, history_end,
        ["SENTINEL-1A_DP_GRD_HIGH", "SENTINEL-1B_DP_GRD_HIGH", "SENTINEL-1C_DP_GRD_HIGH"],
        _s1_platform, footprints, rows,
    )
    if progress_cb:
        progress_cb("Sentinel-1 GRD", n)

    n = _fetch_asf_history(
        bbox, history_start, history_end, ["NISAR_L2_GCOV_PROVISIONAL_V1"], lambda g: "NISAR", footprints, rows
    )
    if progress_cb:
        progress_cb("NISAR L2 GCOV", n)

    history_df = pd.DataFrame(rows)
    if history_df.empty:
        return history_df, footprints
    history_df["time"] = pd.to_datetime(history_df["time"], format="ISO8601", utc=True).dt.tz_localize(None)
    history_df = history_df.sort_values("time").reset_index(drop=True)
    return history_df, footprints


def build_forecast(history_df, today, horizon_days):
    """Detects each platform's real gap pattern and projects it through `horizon_days`."""
    forecast_rows = []
    if history_df.empty:
        return pd.DataFrame(
            columns=["platform", "predicted_datetime_utc", "days_until", "basis", "last_observed"]
        )

    for platform, group in history_df.groupby("platform"):
        nominal_cycle = NOMINAL_REPEAT_CYCLE_DAYS.get(platform)
        if nominal_cycle is None:
            continue

        dates = sorted(group["time"].tolist())
        gaps = [(dates[i + 1] - dates[i]).days for i in range(len(dates) - 1)]
        period = _detect_period(gaps) if len(gaps) >= 2 else None

        last_seen = dates[-1]
        if period:
            pattern = gaps[-period:]
            basis = f"empirical pattern {pattern} (from {len(dates)} recent obs.)"
        else:
            pattern = [nominal_cycle]
            basis = f"nominal {nominal_cycle}-day cycle (only {len(dates)} recent obs. — pattern not confirmed)"

        current = last_seen
        i = 0
        while True:
            gap = pattern[i % len(pattern)]
            current = current + timedelta(days=gap)
            if current.date() > today + timedelta(days=horizon_days):
                break
            if current.date() >= today:
                forecast_rows.append(
                    {
                        "platform": platform,
                        "predicted_datetime_utc": current,
                        "days_until": (current.date() - today).days,
                        "basis": basis,
                        "last_observed": last_seen,
                    }
                )
            i += 1

    return pd.DataFrame(forecast_rows).sort_values("predicted_datetime_utc").reset_index(drop=True)
