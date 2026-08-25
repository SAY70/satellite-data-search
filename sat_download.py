"""Downloads filtered scenes: CMR-sourced products via their real archive
(ASF DAAC / LP DAAC / PO.DAAC), Earth Engine-sourced products clipped to the
AOI. Shared by the download notebook and the dashboard app.
"""

from pathlib import Path
from urllib.parse import urlparse

import asf_search as asf
import ee
import geemap
import pandas as pd
import requests

EE_COLLECTION_BY_PRODUCT = {
    "Sentinel-2 L2A (Surface Reflectance)": "COPERNICUS/S2_SR_HARMONIZED",
    "Sentinel-2 L1C (Top-of-Atmosphere)": "COPERNICUS/S2_HARMONIZED",
    "Landsat 8 C2 L2 (Surface Reflectance)": "LANDSAT/LC08/C02/T1_L2",
    "Landsat 9 C2 L2 (Surface Reflectance)": "LANDSAT/LC09/C02/T1_L2",
    "MODIS Terra Vegetation (NDVI/EVI)": "MODIS/061/MOD13Q1",
    "MODIS Aqua Vegetation (NDVI/EVI)": "MODIS/061/MYD13Q1",
    "MODIS Terra Snow Cover": "MODIS/061/MOD10A1",
    "MODIS Aqua Snow Cover": "MODIS/061/MYD10A1",
}


def safe_name(product):
    return product.replace(" ", "_").replace("(", "").replace(")", "").replace("/", "-")


class _EarthdataSession(requests.Session):
    """NASA's documented Earthdata Login redirect-auth pattern: keeps the
    Authorization header attached across the URS OAuth redirect, but strips
    it once redirected to a third-party host so credentials aren't leaked.
    """

    AUTH_HOST = "urs.earthdata.nasa.gov"

    def __init__(self, username, password):
        super().__init__()
        self.auth = (username, password)

    def rebuild_auth(self, prepared_request, response):
        headers = prepared_request.headers
        url = prepared_request.url
        if "Authorization" in headers:
            original_host = requests.utils.urlparse(response.request.url).hostname
            redirect_host = requests.utils.urlparse(url).hostname
            if original_host != redirect_host and redirect_host != self.AUTH_HOST and original_host != self.AUTH_HOST:
                del headers["Authorization"]
        return


def build_earthdata_sessions(username, password):
    """Returns (earthdata_session, asf_session). Credentials are held only in memory."""
    earthdata_session = _EarthdataSession(username, password)
    asf_session = asf.ASFSession().auth_with_creds(username, password)
    return earthdata_session, asf_session


def download_cmr_rows(rows, download_root, earthdata_session, asf_session, progress_cb=None):
    """Download a subset of CMR-sourced rows (must each have a non-null 'link').

    progress_cb(i, total, message) is called before each file and once more
    at completion (i == total) if given.
    """
    download_root = Path(download_root)
    total = len(rows)
    for i, (_, row) in enumerate(rows.iterrows(), start=1):
        product_dir = download_root / safe_name(row["product"])
        product_dir.mkdir(parents=True, exist_ok=True)
        ext = Path(row["link"]).suffix or ".bin"
        out_path = product_dir / f"{row['id']}{ext}"
        tmp_name = out_path.name + ".part"
        tmp_path = product_dir / tmp_name

        if out_path.exists():
            if progress_cb:
                progress_cb(i, total, f"Skipping (already downloaded): {out_path.name}")
            continue

        size_str = f"{row['size_mb']:.0f} MB" if pd.notna(row.get("size_mb")) else "size unknown"
        if progress_cb:
            progress_cb(i, total, f"Downloading {row['product']} — {row['id']} ({size_str})...")
        try:
            tmp_path.unlink(missing_ok=True)
            is_asf = "asf" in (urlparse(row["link"]).hostname or "").lower()
            if is_asf:
                asf.download_url(url=row["link"], path=str(product_dir), filename=tmp_name, session=asf_session)
            else:
                with earthdata_session.get(row["link"], stream=True, timeout=300) as r:
                    r.raise_for_status()
                    with open(tmp_path, "wb") as f:
                        for chunk in r.iter_content(chunk_size=1024 * 1024):
                            if chunk:
                                f.write(chunk)
            tmp_path.rename(out_path)
        except BaseException:
            tmp_path.unlink(missing_ok=True)
            raise
    if progress_cb:
        progress_cb(total, total, f"Done: {total} row(s) processed.")


def download_ee_rows(rows, download_root, geometry, progress_cb=None):
    """Download a subset of Earth Engine-sourced rows, clipped to the AOI."""
    download_root = Path(download_root)
    total = len(rows)
    for i, (_, row) in enumerate(rows.iterrows(), start=1):
        collection_id = EE_COLLECTION_BY_PRODUCT[row["product"]]
        product_dir = download_root / safe_name(row["product"])
        product_dir.mkdir(parents=True, exist_ok=True)
        out_path = product_dir / f"{row['id']}.tif"

        if out_path.exists():
            if progress_cb:
                progress_cb(i, total, f"Skipping (already downloaded): {out_path.name}")
            continue

        if progress_cb:
            progress_cb(i, total, f"Downloading {row['product']} — {row['id']}...")
        img = ee.Image(f"{collection_id}/{row['id']}").clip(geometry)
        geemap.ee_export_image(
            img, filename=str(out_path), scale=row["resolution_m"], region=geometry, file_per_band=False
        )
    if progress_cb:
        progress_cb(total, total, f"Done: {total} row(s) processed.")


def summarize_downloads(download_root):
    """Returns a DataFrame: one row per downloaded file (product, name, size_mb)."""
    download_root = Path(download_root)
    if not download_root.exists():
        return pd.DataFrame(columns=["product", "file", "size_mb"])
    rows = []
    for f in sorted(download_root.rglob("*")):
        if f.is_file():
            rows.append(
                {
                    "product": f.parent.name,
                    "file": f.name,
                    "size_mb": f.stat().st_size / (1024 ** 2),
                }
            )
    return pd.DataFrame(rows)
