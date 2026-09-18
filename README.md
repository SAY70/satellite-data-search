<p align="center">
  <img src="docs/images/banner.svg" alt="Satellite Data Search Toolkit" width="100%">
</p>

<p align="center">
  <img src="https://img.shields.io/badge/python-3.10%2B-0f766e" alt="Python 3.10+">
  <img src="https://img.shields.io/badge/license-GPL--3.0-0f766e" alt="GPL-3.0 License">
  <img src="https://img.shields.io/badge/built%20with-Streamlit-ff4b4b" alt="Built with Streamlit">
  <img src="https://img.shields.io/badge/Earth%20Engine-supported-34a853" alt="Google Earth Engine">
</p>

An end-to-end toolkit for finding, reviewing, and downloading satellite imagery over an area of interest (AOI), plus tools for planning field data collection around future satellite passes.

Covers **Sentinel-1, Sentinel-2, Landsat 8/9, NISAR, MODIS, and Sentinel-6**, pulling each product from wherever it actually lives — [Google Earth Engine](https://earthengine.google.com/) for what's in its catalog, and each mission's real archive (ASF DAAC, LP DAAC, PO.DAAC via [NASA CMR](https://cmr.earthdata.nasa.gov/)) for what isn't.

Two equivalent ways to use it:
- **An all-in-one interactive dashboard** ([app.py](app.py), built with [Streamlit](https://streamlit.io/))
- **Six numbered Jupyter notebooks**, one per pipeline stage

Both are backed by the exact same underlying code (`sat_search.py`, `sat_download.py`, `sat_forecast.py`, `sat_orbit.py`, `aoi_export.py`) — there's one implementation of each step, not two.

<p align="center">
  <img src="docs/images/pipeline_overview.svg" alt="Pipeline overview: AOI, Search, Download, Forecast, Live Tracker, GitHub" width="100%">
</p>

## Quick start

```bash
git clone https://github.com/SAY70/satellite-data-search.git
cd satellite-data-search
pip install -r requirements.txt
streamlit run app.py
```

**First time?** You'll need your own free Google Earth Engine project, and optionally a NASA Earthdata login for downloads. **[docs/pdf/00_Getting_Started.pdf](docs/pdf/00_Getting_Started.pdf) walks through the whole setup in about 10 minutes**, with no OAuth code to copy/paste.

Every pipeline stage also has its own short PDF guide in [docs/pdf/](docs/pdf/), and is one click away from inside the app (📖 icon on every tab).

---

## See it in action

Real output from a live run over a test AOI near Starkville, Mississippi — 392 scenes found across 4 sensors, filtered down to 181:

<p align="center"><img src="docs/images/app/search_map.png" alt="Search results: 392 scenes found, 181 kept after filtering, with scene footprints drawn over the AOI" width="100%"></p>

---

## The six stages

### 🗺️ 1. AOI Selection

Draw an area of interest on an interactive map — rectangle or polygon, one shape — and export it as GeoJSON, KML, and KMZ. Every later stage reads the same GeoJSON back in.

<p align="center"><img src="docs/images/step1_aoi.svg" alt="AOI selection flow: draw on map, export_all(), writes .geojson/.kml/.kmz" width="90%"></p>

<p align="center"><img src="docs/images/app/aoi.png" alt="AOI tab: drawing tools on a satellite basemap with the saved AOI outlined in red and its area shown" width="100%"></p>

### 🔍 2. Multi-Mission Search

Searches all six sensors over your AOI and date range in one pass, pulling each from wherever it actually lives, and merges everything into one filterable table with coverage %, cloud cover, resolution, and a footprint map.

<p align="center"><img src="docs/images/step2_search.svg" alt="Search flow: AOI splits into Google Earth Engine and NASA CMR archive, merges into combined results table" width="90%"></p>

Every product variant is queried separately, so you can see exactly what each mission did and didn't collect:

<p align="center"><img src="docs/images/app/search_running.png" alt="Search in progress, showing per-product scene counts for every Sentinel, Landsat, NISAR and MODIS product" width="100%"></p>

Results land in a sortable table with everything you need to filter on, and export to CSV:

<p align="center"><img src="docs/images/app/search_table.png" alt="Search results table showing product, sensor, scene id, date, level, resolution and AOI coverage columns" width="100%"></p>

### ⬇️ 3. Download

Pulls the scenes you kept. Earth Engine-sourced products are clipped to your AOI (small, no login); CMR-sourced products (Sentinel-1, NISAR, Sentinel-6, HLS) come from their real archive as full files, and need a free NASA Earthdata login.

<p align="center"><img src="docs/images/step3_download.svg" alt="Download flow: filtered scenes split into Earth Engine clipped download and CMR archive download, both land in downloads folder" width="90%"></p>

### 📅 4. Future Overpass Forecast

Rather than assuming each satellite's textbook nominal revisit cycle, this looks at ~60 days of *actual* recent acquisitions over your specific AOI, detects the real repeating gap pattern, and projects it forward.

<p align="center"><img src="docs/images/step4_forecast.svg" alt="Forecast flow: recent history feeds gap-pattern detection, projected forward into future predicted passes" width="80%"></p>

Each platform's predicted passes, 90 days out — note how MODIS is near-daily while Landsat and Sentinel-2 cluster on their own repeat cycles:

<p align="center"><img src="docs/images/app/forecast_timeline.png" alt="Predicted overpass timeline chart showing per-platform passes for MODIS, NISAR, Sentinel-2 and Landsat" width="100%"></p>

### 🛰️ 5. Live Orbit Tracker

An independent, physics-based cross-check: pulls each satellite's live orbital elements (TLEs) from CelesTrak and propagates them forward with `skyfield` — no Earth Engine, no login, no acquisition history needed.

<p align="center"><img src="docs/images/step5_orbit.svg" alt="Live tracker flow: CelesTrak TLE feeds skyfield orbit propagation, produces real-time ground track vs AOI" width="80%"></p>

<p align="center"><img src="docs/images/app/orbit_map.png" alt="Live orbit tracker map showing current satellite positions and their ground tracks relative to the AOI" width="100%"></p>

### 🔗 6. GitHub Sync

Backs up the project to your own private GitHub repository — creating it automatically the first time, and only committing/pushing when something actually changed. `downloads/` is never pushed (a filename+size manifest is committed instead).

<p align="center"><img src="docs/images/step6_github.svg" alt="GitHub sync flow: local commit, check or create repo via API, git push with token, lands in private GitHub repo" width="95%"></p>

---

## Why the empirical forecast?

Rather than assuming each satellite's textbook nominal revisit cycle (10 days for Sentinel-2, 16 for Landsat, etc.), the forecast step looks at the last ~60 days of *actual* acquisitions over your specific AOI and detects the real repeating gap pattern — which can differ substantially from the nominal figure (e.g. an AOI in the overlap zone between two adjacent orbit paths gets imaged more often than the nominal cycle implies). The Live Orbit Tracker provides an independent, orbit-physics-based cross-check that doesn't depend on acquisition history at all.

## Running the notebooks instead

```bash
jupyter lab
```

Then run, in order: `1_AOI_Selection.ipynb` → `2_Sentinel_Search.ipynb` → `3_Download_Filtered_Scenes.ipynb` → `4_Future_Overpass_Forecast.ipynb` → `5_Live_Orbit_Tracker.ipynb` → (optional) `6_Push_To_GitHub.ipynb`.

## Project structure

```
app.py                    # Streamlit dashboard (all 6 stages in one UI)
sat_search.py             # Multi-mission search (Earth Engine + CMR)
sat_download.py           # Scene download (Earth Engine + CMR)
sat_forecast.py           # Empirical revisit-pattern forecasting
sat_orbit.py               # Live TLE-based orbit tracking
aoi_export.py               # AOI export/import (GeoJSON/KML/KMZ)
1-6_*.ipynb                  # Notebook version of each pipeline stage
docs/pdf/                    # Guide PDFs (source: docs/generate_guides.py)
docs/images/                 # README diagrams (source: docs/generate_diagrams.py)
```

## Requirements

Python 3.10+, and see [requirements.txt](requirements.txt). Free accounts needed: [Google Earth Engine](https://code.earthengine.google.com/register), [NASA Earthdata](https://urs.earthdata.nasa.gov/) (downloads only), [GitHub](https://github.com/) (optional, for the sync feature).

## Contributing

Bug reports, documentation fixes, and new sensors are all welcome — see [CONTRIBUTING.md](CONTRIBUTING.md) for how the code is organized and what it takes to add a mission.

## Security

Credentials are never written to disk by this toolkit. See [SECURITY.md](SECURITY.md) for how each credential is handled and how to report a vulnerability privately.

## License

[GPL-3.0](LICENSE)

## Citing this work

See [CITATION.cff](CITATION.cff).
