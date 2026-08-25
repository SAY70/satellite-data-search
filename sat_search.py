"""Multi-mission scene search: Sentinel-1/2, Landsat, NISAR, MODIS, Sentinel-6.

Pulls each product from wherever it actually lives — Earth Engine for what's
in its catalog, NASA CMR (ASF/LP DAAC/PO.DAAC) for what isn't — and returns
one tidy DataFrame plus a footprints dict for mapping. Shared by the search
notebook and the dashboard app so the search logic exists in exactly one place.
"""

import re

import ee
import pandas as pd
import requests

CMR_GRANULES_URL = "https://cmr.earthdata.nasa.gov/search/granules.json"

SENSOR_COLORS = {
    "Sentinel-1": "#14b8a6",
    "Sentinel-2": "#eab308",
    "Landsat": "#f97316",
    "NISAR": "#a855f7",
    "MODIS": "#0ea5e9",
    "Sentinel-6": "#ec4899",
}

# ---------------------------------------------------------------- products --

S2_EE_PRODUCTS = {
    "Sentinel-2 L2A (Surface Reflectance)": {
        "collection_id": "COPERNICUS/S2_SR_HARMONIZED",
        "resolution_m": 10,
        "level": "L2A",
        "properties": {"cloud_pct": "CLOUDY_PIXEL_PERCENTAGE", "tile": "MGRS_TILE", "platform": "SPACECRAFT_NAME"},
    },
    "Sentinel-2 L1C (Top-of-Atmosphere)": {
        "collection_id": "COPERNICUS/S2_HARMONIZED",
        "resolution_m": 10,
        "level": "L1C",
        "properties": {"cloud_pct": "CLOUDY_PIXEL_PERCENTAGE", "tile": "MGRS_TILE", "platform": "SPACECRAFT_NAME"},
    },
}
S2_CMR_PRODUCTS = {
    "Sentinel-2 HLS S30": {
        "provider": "LPCLOUD",
        "short_names": ["HLSS30"],
        "id_regex": None,
        "resolution_m": 30,
        "level": "HLS S30",
    },
}

_S1_ID_RE = r"^S1[A-Z]_(?P<instrument_mode>IW|EW|SM|WV)_{ptype}(?P<polarization>SH|SV|DH|DV)_"
S1_CMR_PRODUCTS = {
    "Sentinel-1 GRD High-Res (Dual-pol)": {
        "provider": "ASF",
        "short_names": ["SENTINEL-1A_DP_GRD_HIGH", "SENTINEL-1B_DP_GRD_HIGH", "SENTINEL-1C_DP_GRD_HIGH"],
        "id_regex": _S1_ID_RE.format(ptype="GRDH_1S"),
        "resolution_m": 10,
        "level": "GRDH",
    },
    "Sentinel-1 GRD High-Res (Single-pol)": {
        "provider": "ASF",
        "short_names": ["SENTINEL-1A_SP_GRD_HIGH", "SENTINEL-1B_SP_GRD_HIGH", "SENTINEL-1C_SP_GRD_HIGH"],
        "id_regex": _S1_ID_RE.format(ptype="GRDH_1S"),
        "resolution_m": 10,
        "level": "GRDH",
    },
    "Sentinel-1 GRD Medium-Res (Dual-pol)": {
        "provider": "ASF",
        "short_names": ["SENTINEL-1A_DP_GRD_MEDIUM", "SENTINEL-1B_DP_GRD_MEDIUM", "SENTINEL-1C_DP_GRD_MEDIUM"],
        "id_regex": _S1_ID_RE.format(ptype="GRDM_1S"),
        "resolution_m": 40,
        "level": "GRDM",
    },
    "Sentinel-1 SLC": {
        "provider": "ASF",
        "short_names": ["SENTINEL-1A_SLC", "SENTINEL-1B_SLC", "SENTINEL-1C_SLC"],
        "id_regex": _S1_ID_RE.format(ptype="SLC__1S"),
        "resolution_m": 5,
        "level": "SLC",
    },
    "Sentinel-1 OCN": {
        "provider": "ASF",
        "short_names": ["SENTINEL-1A_OCN", "SENTINEL-1B_OCN", "SENTINEL-1C_OCN"],
        "id_regex": _S1_ID_RE.format(ptype="OCN__2S"),
        "resolution_m": None,
        "level": "OCN",
    },
}

_NISAR_ID_RE = r"^NISAR_L\d_PR_[A-Z0-9]+_\d+_\d+_(?P<orbit_pass>[AD])_"
NISAR_CMR_PRODUCTS = {
    "NISAR L2 GCOV (Geocoded Covariance)": {
        "provider": "ASF",
        "short_names": ["NISAR_L2_GCOV_PROVISIONAL_V1"],
        "id_regex": _NISAR_ID_RE,
        "resolution_m": 20,
        "level": "L2 GCOV",
    },
    "NISAR L1 RSLC (Range-Doppler Complex)": {
        "provider": "ASF",
        "short_names": ["NISAR_L1_RSLC_PROVISIONAL_V1"],
        "id_regex": _NISAR_ID_RE,
        "resolution_m": 5,
        "level": "L1 RSLC",
    },
    "NISAR L3 Soil Moisture": {
        "provider": "ASF",
        "short_names": ["NISAR_L3_SME2_PROVISIONAL_V1"],
        "id_regex": _NISAR_ID_RE,
        "resolution_m": 1000,
        "level": "L3 SME2",
    },
}

LANDSAT_EE_PRODUCTS = {
    "Landsat 8 C2 L2 (Surface Reflectance)": {
        "collection_id": "LANDSAT/LC08/C02/T1_L2",
        "resolution_m": 30,
        "level": "L2 SR",
        "properties": {
            "cloud_pct": "CLOUD_COVER",
            "path": "WRS_PATH",
            "row": "WRS_ROW",
            "platform": "SPACECRAFT_ID",
            "instrument": "SENSOR_ID",
        },
    },
    "Landsat 9 C2 L2 (Surface Reflectance)": {
        "collection_id": "LANDSAT/LC09/C02/T1_L2",
        "resolution_m": 30,
        "level": "L2 SR",
        "properties": {
            "cloud_pct": "CLOUD_COVER",
            "path": "WRS_PATH",
            "row": "WRS_ROW",
            "platform": "SPACECRAFT_ID",
            "instrument": "SENSOR_ID",
        },
    },
}
LANDSAT_CMR_PRODUCTS = {
    "Landsat HLS L30": {
        "provider": "LPCLOUD",
        "short_names": ["HLSL30"],
        "id_regex": None,
        "resolution_m": 30,
        "level": "HLS L30",
    },
}

MODIS_EE_PRODUCTS = {
    "MODIS Terra Vegetation (NDVI/EVI)": {
        "collection_id": "MODIS/061/MOD13Q1",
        "resolution_m": 250,
        "level": "L3 VI 16-day",
        "properties": {},
    },
    "MODIS Aqua Vegetation (NDVI/EVI)": {
        "collection_id": "MODIS/061/MYD13Q1",
        "resolution_m": 250,
        "level": "L3 VI 16-day",
        "properties": {},
    },
    "MODIS Terra Snow Cover": {
        "collection_id": "MODIS/061/MOD10A1",
        "resolution_m": 500,
        "level": "L3 Snow Daily",
        "properties": {},
    },
    "MODIS Aqua Snow Cover": {
        "collection_id": "MODIS/061/MYD10A1",
        "resolution_m": 500,
        "level": "L3 Snow Daily",
        "properties": {},
    },
}

S6_CMR_PRODUCTS = {
    "Sentinel-6 Low-Res OST (NTC)": {
        "provider": "POCLOUD",
        "short_names": ["JASON_CS_S6A_L2_ALT_LR_STD_OST_NTC_F08"],
        "id_regex": None,
        "resolution_m": None,
        "level": "L2 ALT LR OST NTC",
    },
}

# Sensor name -> (ee_products, cmr_products), either half may be {}
SENSOR_PRODUCTS = {
    "Sentinel-2": (S2_EE_PRODUCTS, S2_CMR_PRODUCTS),
    "Sentinel-1": ({}, S1_CMR_PRODUCTS),
    "Landsat": (LANDSAT_EE_PRODUCTS, LANDSAT_CMR_PRODUCTS),
    "NISAR": ({}, NISAR_CMR_PRODUCTS),
    "MODIS": (MODIS_EE_PRODUCTS, {}),
    "Sentinel-6": ({}, S6_CMR_PRODUCTS),
}

# --------------------------------------------------------------- helpers ---


def _aoi_coverage_pct(image_geom, aoi):
    aoi_area = aoi.area(1)
    inter_area = image_geom.intersection(aoi, 1).area(1)
    return inter_area.divide(aoi_area).multiply(100)


def _sensor_from_product(label):
    return label.split()[0]


def _tidy(df):
    if df.empty:
        return df
    front = ["product", "sensor", "id", "date", "level", "resolution_m", "aoi_cov_pct", "cloud_pct"]
    front = [c for c in front if c in df.columns]
    df = df[front + [c for c in df.columns if c not in front]]
    return df.sort_values(["product", "date"]).reset_index(drop=True)


def search_ee_products(products, aoi, start_date, end_date, footprints, progress_cb=None):
    """products: {label: {'collection_id','resolution_m','level','properties'}} -> DataFrame.

    Writes each row's real footprint into `footprints`, keyed by (label, id).
    """
    rows = []
    for label, cfg in products.items():
        collection = ee.ImageCollection(cfg["collection_id"]).filterBounds(aoi).filterDate(start_date, end_date)
        prop_map = cfg.get("properties", {})

        def add_props(image, prop_map=prop_map):
            props = {
                "id": image.get("system:index"),
                "date": image.date().format("YYYY-MM-dd HH:mm"),
                "aoi_cov_pct": _aoi_coverage_pct(image.geometry(), aoi),
            }
            for out_col, ee_prop in prop_map.items():
                props[out_col] = image.get(ee_prop)
            return ee.Feature(image.geometry(), props)

        fc = ee.FeatureCollection(collection.map(add_props))
        info = fc.getInfo()
        if progress_cb:
            progress_cb(label, len(info["features"]))
        for feature in info["features"]:
            row = feature["properties"]
            row["product"] = label
            row["sensor"] = _sensor_from_product(label)
            row["resolution_m"] = cfg.get("resolution_m")
            row["level"] = cfg.get("level")
            footprints[(label, row["id"])] = feature["geometry"]
            rows.append(row)

    return _tidy(pd.DataFrame(rows))


def _cmr_bbox(aoi):
    coords = aoi.bounds(1).coordinates().getInfo()[0]
    lons = [c[0] for c in coords]
    lats = [c[1] for c in coords]
    return f"{min(lons)},{min(lats)},{max(lons)},{max(lats)}"


def _granule_footprint(granule):
    polygons = granule.get("polygons")
    if not polygons:
        return None
    ring = polygons[0][0].split()
    points = [[float(ring[i + 1]), float(ring[i])] for i in range(0, len(ring), 2)]
    return {"type": "Polygon", "coordinates": [points]}


def _granule_link(granule):
    data_links = [l["href"] for l in granule.get("links", []) if "/data#" in l.get("rel", "")]
    zip_links = [href for href in data_links if href.lower().endswith(".zip")]
    if zip_links:
        return zip_links[0]
    return data_links[0] if data_links else None


def search_cmr_products(products, aoi, start_date, end_date, footprints, page_size=200, progress_cb=None):
    """products: {label: {'provider','short_names','id_regex','resolution_m','level'}} -> DataFrame."""
    rows = []
    for label, cfg in products.items():
        params = [("short_name", s) for s in cfg["short_names"]]
        params += [
            ("provider", cfg["provider"]),
            ("bounding_box", _cmr_bbox(aoi)),
            ("temporal", f"{start_date}T00:00:00Z,{end_date}T23:59:59Z"),
            ("page_size", str(page_size)),
        ]
        resp = requests.get(CMR_GRANULES_URL, params=params, timeout=60)
        resp.raise_for_status()
        entries = resp.json()["feed"]["entry"]
        if progress_cb:
            progress_cb(label, len(entries))

        id_regex = re.compile(cfg["id_regex"]) if cfg.get("id_regex") else None
        for g in entries:
            granule_id = g.get("producer_granule_id") or g.get("title", "")
            match = id_regex.match(granule_id) if id_regex else None
            footprint = _granule_footprint(g)
            cov_pct = _aoi_coverage_pct(ee.Geometry(footprint), aoi).getInfo() if footprint else None
            if footprint:
                footprints[(label, granule_id)] = footprint
            row = {
                "product": label,
                "sensor": _sensor_from_product(label),
                "id": granule_id,
                "date": g.get("time_start"),
                "resolution_m": cfg.get("resolution_m"),
                "level": cfg.get("level"),
                "aoi_cov_pct": cov_pct,
                "cloud_pct": float(g["cloud_cover"]) if g.get("cloud_cover") not in (None, "") else None,
                "size_mb": float(g["granule_size"]) if g.get("granule_size") not in (None, "") else None,
                "link": _granule_link(g),
            }
            if match:
                row.update(match.groupdict())
            rows.append(row)

    return _tidy(pd.DataFrame(rows))


def search_all(aoi, start_date, end_date, sensors=None, progress_cb=None):
    """Search the given sensors (default: all six) over the AOI/date range.

    Returns (results_df, footprints). `progress_cb(label, count)` is called
    once per product searched, for live progress reporting.
    """
    sensors = sensors or list(SENSOR_PRODUCTS)
    footprints = {}
    frames = []
    for sensor in sensors:
        ee_products, cmr_products = SENSOR_PRODUCTS[sensor]
        if ee_products:
            frames.append(search_ee_products(ee_products, aoi, start_date, end_date, footprints, progress_cb))
        if cmr_products:
            frames.append(search_cmr_products(cmr_products, aoi, start_date, end_date, footprints, progress_cb=progress_cb))
    results_df = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()
    return results_df, footprints


def filter_scenes(results_df, min_aoi_cov_pct=50, max_cloud_pct=30):
    if results_df.empty:
        return results_df.copy()
    if "cloud_pct" in results_df.columns:
        cloud_ok = results_df["cloud_pct"].isna() | (results_df["cloud_pct"] <= max_cloud_pct)
    else:
        cloud_ok = pd.Series(True, index=results_df.index)
    return results_df[(results_df["aoi_cov_pct"] >= min_aoi_cov_pct) & cloud_ok].reset_index(drop=True)
