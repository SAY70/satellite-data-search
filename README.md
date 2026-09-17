# 🛰️ Satellite Data Search Toolkit

An end-to-end toolkit for finding, reviewing, and downloading satellite imagery over an area of interest (AOI), plus tools for planning field data collection around future satellite passes.

Covers **Sentinel-1, Sentinel-2, Landsat 8/9, NISAR, MODIS, and Sentinel-6**, pulling each product from wherever it actually lives — [Google Earth Engine](https://earthengine.google.com/) for what's in its catalog, and each mission's real archive (ASF DAAC, LP DAAC, PO.DAAC via [NASA CMR](https://cmr.earthdata.nasa.gov/)) for what isn't.

Two equivalent ways to use it:
- **An all-in-one interactive dashboard** ([app.py](app.py), built with [Streamlit](https://streamlit.io/))
- **Six numbered Jupyter notebooks**, one per pipeline stage

Both are backed by the exact same underlying code (`sat_search.py`, `sat_download.py`, `sat_forecast.py`, `sat_orbit.py`, `aoi_export.py`) — there's one implementation of each step, not two.

## Features

| Stage | What it does |
|---|---|
| 🗺️ **AOI Selection** | Draw an area of interest on a map, export as GeoJSON/KML/KMZ |
| 🔍 **Multi-Mission Search** | Search all 6 sensors over your AOI and date range, filter by coverage/cloud cover, visualize footprints on a map |
| ⬇️ **Download** | Pull filtered scenes — clipped GeoTIFFs from Earth Engine, or full original files from the real archive |
| 📅 **Overpass Forecast** | Predict future satellite passes from *real recent acquisition patterns*, not textbook nominal cycles |
| 🛰️ **Live Orbit Tracker** | Real-time satellite positions and physics-based overpass predictions from live TLEs — no Earth Engine needed |
| 🔗 **GitHub Sync** | Back up the project to your own private GitHub repository |

## Quick start

```bash
git clone https://github.com/SAY70/satellite-data-search.git
cd satellite-data-search
pip install -r requirements.txt
streamlit run app.py
```

**First time?** You'll need your own free Google Earth Engine project (the one baked into this repo belongs to the original author and won't work for you), and optionally a NASA Earthdata login for downloads. **[docs/pdf/00_Getting_Started.pdf](docs/pdf/00_Getting_Started.pdf) walks through the whole setup in about 10 minutes**, with no OAuth code to copy/paste.

Every pipeline stage also has its own short PDF guide in [docs/pdf/](docs/pdf/), and is one click away from inside the app (📖 icon on every tab).

## Running the notebooks instead

```bash
jupyter lab
```

Then run, in order: `1_AOI_Selection.ipynb` → `2_Sentinel_Search.ipynb` → `3_Download_Filtered_Scenes.ipynb` → `4_Future_Overpass_Forecast.ipynb` → `5_Live_Orbit_Tracker.ipynb` → (optional) `6_Push_To_GitHub.ipynb`.

## Why the empirical forecast?

Rather than assuming each satellite's textbook nominal revisit cycle (10 days for Sentinel-2, 16 for Landsat, etc.), the forecast step looks at the last ~60 days of *actual* acquisitions over your specific AOI and detects the real repeating gap pattern — which can differ substantially from the nominal figure (e.g. an AOI in the overlap zone between two adjacent orbit paths gets imaged more often than the nominal cycle implies). The Live Orbit Tracker provides an independent, orbit-physics-based cross-check that doesn't depend on acquisition history at all.

## Project structure

```
app.py                    # Streamlit dashboard (all 6 stages in one UI)
sat_search.py             # Multi-mission search (Earth Engine + CMR)
sat_download.py           # Scene download (Earth Engine + CMR)
sat_forecast.py           # Empirical revisit-pattern forecasting
sat_orbit.py               # Live TLE-based orbit tracking
aoi_export.py              # AOI export/import (GeoJSON/KML/KMZ)
1-6_*.ipynb                 # Notebook version of each pipeline stage
docs/pdf/                   # Guide PDFs (also generated from docs/generate_guides.py)
```

## Requirements

Python 3.10+, and see [requirements.txt](requirements.txt). Free accounts needed: [Google Earth Engine](https://code.earthengine.google.com/register), [NASA Earthdata](https://urs.earthdata.nasa.gov/) (downloads only), [GitHub](https://github.com/) (optional, for the sync feature).

## License

[MIT](LICENSE)

## Citing this work

See [CITATION.cff](CITATION.cff).
