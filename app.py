"""Satellite Data Search Toolkit — one interactive dashboard covering the
whole pipeline: draw an AOI, search Sentinel-1/2, Landsat, NISAR, MODIS and
Sentinel-6, review results on a map, download filtered scenes, forecast
future overpasses, track satellites live, and sync the project to GitHub.

All the actual logic lives in sat_search.py / sat_download.py /
sat_forecast.py / sat_orbit.py / aoi_export.py — this file is the UI layer
on top of them, so there's exactly one implementation of each pipeline step
whether you drive it from here or from the numbered notebooks.

Run with:  streamlit run app.py
"""

import json
import subprocess
from datetime import date, datetime, timedelta
from pathlib import Path

import ee
import folium
import pandas as pd
import plotly.express as px
import streamlit as st
from folium.plugins import Draw
from streamlit_folium import st_folium

import sat_download
import sat_forecast
import sat_orbit
import sat_search
from aoi_export import export_all, load_geometry

# --------------------------------------------------------------- page setup --

st.set_page_config(page_title="Satellite Data Search Toolkit", page_icon="🛰️", layout="wide")

ESRI_IMAGERY = "https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}"
ESRI_ATTR = "Tiles &copy; Esri"


def esri_map(location, zoom):
    m = folium.Map(location=location, zoom_start=zoom, tiles=None)
    folium.TileLayer(tiles=ESRI_IMAGERY, attr=ESRI_ATTR, name="Esri Satellite", overlay=False, control=True).add_to(m)
    folium.TileLayer("OpenStreetMap", name="OpenStreetMap").add_to(m)
    return m


def outline_style(color):
    return lambda _: {"color": color, "weight": 2, "fillOpacity": 0}


# ------------------------------------------------------------------- guides --

GUIDES_DIR = Path(__file__).parent / "docs" / "pdf"
GUIDES = {
    "getting_started": ("00_Getting_Started.pdf", "Getting Started", "Your own accounts, connected from scratch"),
    "aoi": ("01_AOI_Selection_Guide.pdf", "AOI Selection Guide", "How to draw and size your area of interest"),
    "search": ("02_Search_Guide.pdf", "Search Guide", "Reading results, filters, and why a sensor shows 0"),
    "download": ("03_Download_Guide.pdf", "Download Guide", "Credentials, sizes, and the ASF one-time step"),
    "forecast": ("04_Forecast_Guide.pdf", "Forecast Guide", "How to read predicted-overpass confidence"),
    "orbit": ("05_Live_Tracker_Guide.pdf", "Live Tracker Guide", "What physics-based tracking can and can't tell you"),
    "github": ("06_GitHub_Sync_Guide.pdf", "GitHub Sync Guide", "Personal Access Tokens, step by step"),
    "troubleshooting": ("07_Troubleshooting.pdf", "Troubleshooting", "Common errors, what causes them, how to fix them"),
}


def guide_expander(key, label="📖 Need help with this step?"):
    """Small expander with a download button + inline preview for one guide PDF."""
    filename, title, blurb = GUIDES[key]
    path = GUIDES_DIR / filename
    if not path.exists():
        return
    pdf_bytes = path.read_bytes()
    with st.expander(label):
        st.caption(f"**{title}** — {blurb}")
        st.download_button("⬇️ Download PDF", pdf_bytes, filename, "application/pdf", key=f"dl_{key}")
        import base64

        b64 = base64.b64encode(pdf_bytes).decode()
        st.markdown(
            f'<iframe src="data:application/pdf;base64,{b64}" width="100%" height="500" '
            f'style="border:1px solid #cbd5e1;border-radius:6px;"></iframe>',
            unsafe_allow_html=True,
        )


# ------------------------------------------------------------- session init --

defaults = {
    "ee_ready": False,
    "aoi_geometry": None,
    "aoi_name": None,
    "drawn_coords": None,
    "results_df": None,
    "footprints": {},
    "history_df": None,
    "history_footprints": {},
    "forecast_df": None,
    "orbit_ts": None,
    "orbit_sats": None,
    "orbit_snapshot": None,
    "orbit_forecast_df": None,
    "orbit_time": None,
    "search_log": [],
}
for k, v in defaults.items():
    st.session_state.setdefault(k, v)

# ------------------------------------------------------------------ sidebar --

with st.sidebar:
    st.title("🛰️ Mission Control")

    st.subheader("Project config")
    ee_project = st.text_input(
        "Earth Engine project", value="", placeholder="your-gee-project-id",
        help="Your own Google Cloud project ID with the Earth Engine API enabled. "
             "Register one free at https://code.earthengine.google.com/register — see the "
             "Getting Started guide (Overview or Help tab) if you don't have one yet.",
    )
    aoi_name = st.text_input("AOI name", value="my_aoi")
    output_dir = st.text_input("Output folder", value="output")
    download_dir = st.text_input("Download folder", value="downloads")
    st.session_state["aoi_name"] = aoi_name

    if st.button("Connect to Earth Engine", type="primary" if not st.session_state["ee_ready"] else "secondary"):
        if not ee_project.strip():
            st.error(
                "Enter your Earth Engine project ID first — register one free at "
                "https://code.earthengine.google.com/register"
            )
            st.stop()
        try:
            ee.Initialize(project=ee_project)
            st.session_state["ee_ready"] = True
            st.success("Earth Engine connected.")
        except Exception:
            try:
                with st.spinner("Opening your browser to sign in to Google — approve access there, this will finish automatically..."):
                    # auth_mode="localhost": a local server on this machine catches
                    # the OAuth redirect, so there's no code to copy/paste back here.
                    ee.Authenticate(auth_mode="localhost")
                    ee.Initialize(project=ee_project)
                st.session_state["ee_ready"] = True
                st.success("Earth Engine connected.")
            except Exception as e2:
                st.error(f"Could not connect: {e2}")

    if st.session_state["ee_ready"] and st.session_state["aoi_geometry"] is None:
        geojson_path = Path(output_dir) / f"{aoi_name}.geojson"
        if geojson_path.exists():
            try:
                st.session_state["aoi_geometry"] = load_geometry(geojson_path)
            except Exception:
                pass

    st.divider()
    st.subheader("Pipeline status")
    downloads_present = Path(download_dir).exists() and any(Path(download_dir).rglob("*.*"))
    steps = [
        ("Earth Engine connected", st.session_state["ee_ready"]),
        ("AOI selected", st.session_state["aoi_geometry"] is not None),
        ("Scenes searched", st.session_state["results_df"] is not None and not st.session_state["results_df"].empty
         if isinstance(st.session_state["results_df"], pd.DataFrame) else False),
        ("Scenes downloaded", downloads_present),
        ("Forecast generated", st.session_state["forecast_df"] is not None),
        ("Live tracker refreshed", st.session_state["orbit_snapshot"] is not None),
    ]
    for label, done in steps:
        st.markdown(f"{'✅' if done else '⬜'} {label}")

# ------------------------------------------------------------------- tabs ---

tab_home, tab_aoi, tab_search, tab_download, tab_forecast, tab_orbit, tab_github, tab_help = st.tabs(
    ["🏠 Overview", "🗺️ AOI", "🔍 Search", "⬇️ Download", "📅 Forecast", "🛰️ Live Tracker", "🔗 GitHub", "📖 Help"]
)

# ============================================================== 0. OVERVIEW =
with tab_home:
    st.header("Satellite Data Search Toolkit")
    st.write(
        "An end-to-end pipeline for finding, reviewing, and downloading satellite imagery over an "
        "area of interest, plus tools for planning field campaigns around future satellite passes."
    )

    if not st.session_state["ee_ready"]:
        st.info(
            "👋 **First time here?** You'll need your own free Google Earth Engine project (not the "
            "author's) before anything connects — the **Getting Started** guide below walks through "
            "every account you need, step by step, in about 10 minutes."
        )
        guide_expander("getting_started", label="📖 Open the Getting Started guide")

    # Each row: (tab label as shown in the tab bar, what it does, is it done?)
    # "Done" drives the ▶ marker so this panel tells you which tab to click next.
    stages = [
        ("🗺️ AOI", "Draw an area of interest and export it",
         st.session_state["aoi_geometry"] is not None),
        ("🔍 Search", "Find scenes across Sentinel-1/2, Landsat, NISAR, MODIS, Sentinel-6",
         isinstance(st.session_state["results_df"], pd.DataFrame) and not st.session_state["results_df"].empty),
        ("⬇️ Download", "Pull the filtered scenes to disk",
         downloads_present),
        ("📅 Forecast", "Predict future overpasses from real acquisition patterns",
         st.session_state["forecast_df"] is not None),
        ("🛰️ Live Tracker", "Real-time satellite positions via TLE propagation",
         st.session_state["orbit_snapshot"] is not None),
        ("🔗 GitHub", "Push the project to a private repo",
         False),  # no reliable signal, so never marked done
    ]

    next_stage = next((label for label, _, done in stages if not done), None)
    if st.session_state["ee_ready"] and next_stage:
        st.success(f"**Next step:** open the **{next_stage}** tab above.")

    st.markdown("#### Pipeline")
    for i, (label, desc, done) in enumerate(stages, start=1):
        marker = "✅" if done else ("▶️" if label == next_stage else "⬜")
        emphasis = "**" if label == next_stage else ""
        st.markdown(f"{marker} &nbsp; {emphasis}{i}. {label}{emphasis} — {desc}")

    st.caption("Use the tabs at the top of the page to move between steps.")

    st.divider()
    if isinstance(st.session_state["results_df"], pd.DataFrame) and not st.session_state["results_df"].empty:
        st.subheader("Latest search snapshot")
        df = st.session_state["results_df"]
        c1, c2, c3 = st.columns(3)
        c1.metric("Total scenes found", len(df))
        c2.metric("Sensors covered", df["sensor"].nunique())
        c3.metric("Date span (days)", int((pd.to_datetime(df["date"], format="ISO8601", utc=True).max() -
                                            pd.to_datetime(df["date"], format="ISO8601", utc=True).min()).days) if len(df) > 1 else 0)
        fig = px.bar(
            df["sensor"].value_counts().reset_index(), x="sensor", y="count",
            color="sensor", color_discrete_map=sat_search.SENSOR_COLORS, title="Scenes by sensor",
        )
        fig.update_layout(showlegend=False, height=320)
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("Run a search from the **Search** tab to see a summary here.")

# =================================================================== 1. AOI =
with tab_aoi:
    st.header("Area of Interest")
    guide_expander("aoi")

    if not st.session_state["ee_ready"]:
        st.warning("Connect to Earth Engine from the sidebar first.")
    else:
        left, right = st.columns([3, 1])

        with left:
            existing = st.session_state["aoi_geometry"]
            if existing is not None:
                center = existing.centroid(1).coordinates().getInfo()[::-1]
            else:
                center = [33.47, -88.77]

            m = esri_map(center, 11)
            if existing is not None:
                folium.GeoJson(
                    existing.getInfo(), name="Current AOI",
                    style_function=outline_style("#ef4444"), tooltip="Saved AOI",
                ).add_to(m)
            Draw(
                export=False,
                draw_options={
                    "polygon": True, "rectangle": True, "circle": False,
                    "marker": False, "circlemarker": False, "polyline": False,
                },
                edit_options={"edit": True},
            ).add_to(m)
            folium.LayerControl().add_to(m)

            map_data = st_folium(m, key="aoi_draw_map", width=None, height=550)
            if map_data and map_data.get("last_active_drawing"):
                st.session_state["drawn_coords"] = map_data["last_active_drawing"]["geometry"]["coordinates"]

        with right:
            st.markdown("**Instructions**")
            st.caption("Use the polygon or rectangle tool (top-left of the map) to draw your AOI, then save it below.")

            if st.session_state["drawn_coords"]:
                st.success("Shape drawn — ready to save.")
                if st.button("💾 Save as AOI", type="primary"):
                    geometry = ee.Geometry.Polygon(st.session_state["drawn_coords"])
                    paths = export_all(geometry, output_dir, aoi_name)
                    st.session_state["aoi_geometry"] = geometry
                    st.success(f"Saved to {Path(output_dir).resolve()}")
                    for fmt, p in paths.items():
                        st.caption(f"{fmt.upper()}: {p.name}")

            if st.session_state["aoi_geometry"] is not None:
                st.divider()
                area_km2 = st.session_state["aoi_geometry"].area(1).divide(1e6).getInfo()
                st.metric("Current AOI area", f"{area_km2:,.2f} km²")

# ================================================================ 2. SEARCH =
with tab_search:
    st.header("Multi-Mission Scene Search")
    guide_expander("search")

    if st.session_state["aoi_geometry"] is None:
        st.warning("Select an AOI in the **AOI** tab first.")
    else:
        c1, c2 = st.columns(2)
        start_date = c1.date_input("Start date", value=date.today() - timedelta(days=60))
        end_date = c2.date_input("End date", value=date.today())

        sensors = st.multiselect(
            "Sensors", list(sat_search.SENSOR_PRODUCTS), default=list(sat_search.SENSOR_PRODUCTS)
        )

        if st.button("🔍 Run Search", type="primary", disabled=not sensors):
            log_box = st.empty()
            log_lines = []

            def _progress(label, count):
                log_lines.append(f"{label}: {count} scene(s)")
                log_box.code("\n".join(log_lines))

            with st.spinner("Searching Earth Engine and NASA CMR..."):
                results_df, footprints = sat_search.search_all(
                    st.session_state["aoi_geometry"], str(start_date), str(end_date), sensors, progress_cb=_progress
                )
            st.session_state["results_df"] = results_df
            st.session_state["footprints"] = footprints
            st.success(f"Found {len(results_df)} scene(s) across {results_df['sensor'].nunique() if not results_df.empty else 0} sensor(s).")

        results_df = st.session_state["results_df"]
        if isinstance(results_df, pd.DataFrame) and not results_df.empty:
            st.divider()
            st.subheader("Filter")
            fc1, fc2 = st.columns(2)
            min_cov = fc1.slider("Minimum AOI coverage (%)", 0, 100, 50)
            max_cloud = fc2.slider("Maximum cloud cover (%)", 0, 100, 30)
            filtered_df = sat_search.filter_scenes(results_df, min_cov, max_cloud)

            m1, m2, m3 = st.columns(3)
            m1.metric("Total found", len(results_df))
            m2.metric("Kept after filter", len(filtered_df))
            m3.metric("Sensors", filtered_df["sensor"].nunique() if not filtered_df.empty else 0)

            tbl_tab, chart_tab, map_tab = st.tabs(["Table", "Charts", "Map"])
            with tbl_tab:
                st.dataframe(filtered_df, use_container_width=True, height=400)
                csv_bytes = filtered_df.to_csv(index=False).encode("utf-8")
                dc1, dc2 = st.columns(2)
                if dc1.download_button("⬇️ Download filtered CSV", csv_bytes, f"{aoi_name}_scene_search.csv", "text/csv"):
                    pass
                if dc2.button("💾 Save CSV to output/"):
                    out_csv = Path(output_dir) / f"{aoi_name}_scene_search.csv"
                    filtered_df.to_csv(out_csv, index=False)
                    st.success(f"Saved to {out_csv.resolve()}")

            with chart_tab:
                cc1, cc2 = st.columns(2)
                with cc1:
                    fig = px.bar(
                        filtered_df["product"].value_counts().reset_index(), x="count", y="product",
                        orientation="h", title="Scenes by product",
                    )
                    fig.update_layout(height=450, yaxis_title="", xaxis_title="Scenes")
                    st.plotly_chart(fig, use_container_width=True)
                with cc2:
                    if "cloud_pct" in filtered_df.columns and filtered_df["cloud_pct"].notna().any():
                        fig2 = px.histogram(filtered_df, x="cloud_pct", color="sensor",
                                             color_discrete_map=sat_search.SENSOR_COLORS, title="Cloud cover distribution")
                        fig2.update_layout(height=450)
                        st.plotly_chart(fig2, use_container_width=True)
                    else:
                        fig2 = px.histogram(filtered_df, x="aoi_cov_pct", color="sensor",
                                             color_discrete_map=sat_search.SENSOR_COLORS, title="AOI coverage distribution")
                        fig2.update_layout(height=450)
                        st.plotly_chart(fig2, use_container_width=True)

            with map_tab:
                center = st.session_state["aoi_geometry"].centroid(1).coordinates().getInfo()[::-1]
                fmap = esri_map(center, 10)
                folium.GeoJson(st.session_state["aoi_geometry"].getInfo(), name="AOI",
                                style_function=outline_style("#ef4444")).add_to(fmap)
                footprints = st.session_state["footprints"]
                for sensor, color in sat_search.SENSOR_COLORS.items():
                    subset = filtered_df[filtered_df["sensor"] == sensor]
                    if subset.empty:
                        continue
                    group = folium.FeatureGroup(name=f"{sensor} ({len(subset)})")
                    for _, row in subset.iterrows():
                        fp = footprints.get((row["product"], row["id"]))
                        if fp:
                            folium.GeoJson(fp, style_function=outline_style(color), tooltip=row["id"]).add_to(group)
                    group.add_to(fmap)
                folium.LayerControl().add_to(fmap)
                st_folium(fmap, key="search_map", width=None, height=500)

# ============================================================== 3. DOWNLOAD =
with tab_download:
    st.header("Download Filtered Scenes")
    guide_expander("download")

    scenes_source = st.session_state["results_df"]
    csv_path = Path(output_dir) / f"{aoi_name}_scene_search.csv"
    if (scenes_source is None or (isinstance(scenes_source, pd.DataFrame) and scenes_source.empty)) and csv_path.exists():
        scenes_source = pd.read_csv(csv_path)

    if scenes_source is None or scenes_source.empty:
        st.warning("No scene list yet — run a search (and save the CSV) first.")
    else:
        st.caption(f"Working from {len(scenes_source)} scene(s).")
        size_col = scenes_source["size_mb"] if "size_mb" in scenes_source.columns else 0.0
        sensor_counts = (
            scenes_source.assign(_size_mb=size_col)
            .groupby("sensor")
            .agg(files=("id", "count"), total_mb=("_size_mb", lambda s: s.fillna(0).sum()))
            .reset_index()
        )
        st.dataframe(sensor_counts, use_container_width=True)

        selected_sensors = st.multiselect(
            "Sensors to download", sorted(scenes_source["sensor"].unique()), default=[]
        )

        st.divider()
        st.subheader("Earthdata credentials")
        st.caption("Needed for CMR-sourced products (Sentinel-1, NISAR, Sentinel-6, HLS). Held only in memory for this session.")
        ec1, ec2 = st.columns(2)
        ed_user = ec1.text_input("Earthdata username / email", value="")
        ed_pass = ec2.text_input("Earthdata password", type="password", value="")

        confirm = st.checkbox("I understand this will download real data to disk and want to proceed.")

        if st.button("⬇️ Start Download", type="primary", disabled=not (selected_sensors and confirm)):
            rows = scenes_source[scenes_source["sensor"].isin(selected_sensors)]
            ee_rows = rows[rows["product"].isin(sat_download.EE_COLLECTION_BY_PRODUCT)]
            cmr_rows = rows[rows["link"].notna()] if "link" in rows.columns else rows.iloc[0:0]

            progress = st.progress(0.0)
            status = st.empty()
            total = len(ee_rows) + len(cmr_rows)
            done_ee = {"n": 0}

            def _ee_progress(i, total_i, msg):
                status.write(msg)
                progress.progress(min(1.0, i / total) if total else 1.0)
                done_ee["n"] = i

            def _cmr_progress(i, total_i, msg):
                status.write(msg)
                progress.progress(min(1.0, (done_ee["n"] + i) / total) if total else 1.0)

            try:
                if not ee_rows.empty:
                    if not st.session_state["ee_ready"]:
                        st.error("Connect to Earth Engine first (sidebar).")
                    else:
                        sat_download.download_ee_rows(ee_rows, download_dir, st.session_state["aoi_geometry"], progress_cb=_ee_progress)
                if not cmr_rows.empty:
                    if not ed_user or not ed_pass:
                        st.error("Earthdata credentials required for CMR-sourced rows.")
                    else:
                        earthdata_session, asf_session = sat_download.build_earthdata_sessions(ed_user, ed_pass)
                        sat_download.download_cmr_rows(cmr_rows, download_dir, earthdata_session, asf_session, progress_cb=_cmr_progress)
                progress.progress(1.0)
                st.success("Download complete.")
            except Exception as e:
                st.error(f"Download failed: {e}")

        st.divider()
        st.subheader("What's on disk")
        summary_df = sat_download.summarize_downloads(download_dir)
        if summary_df.empty:
            st.caption("Nothing downloaded yet.")
        else:
            st.metric("Total downloaded", f"{summary_df['size_mb'].sum():,.1f} MB across {len(summary_df)} file(s)")
            fig = px.bar(summary_df.groupby("product")["size_mb"].sum().reset_index(),
                         x="product", y="size_mb", title="Downloaded size by product")
            fig.update_layout(height=350, yaxis_title="MB")
            st.plotly_chart(fig, use_container_width=True)
            st.dataframe(summary_df, use_container_width=True, height=250)

# ============================================================== 4. FORECAST =
with tab_forecast:
    st.header("Future Overpass Forecast")
    st.caption("Detects each platform's real recent revisit pattern (not just the textbook nominal cycle) and projects it forward.")
    guide_expander("forecast")

    if st.session_state["aoi_geometry"] is None:
        st.warning("Select an AOI in the **AOI** tab first.")
    else:
        fc1, fc2 = st.columns(2)
        lookback_days = fc1.slider("History lookback (days)", 14, 120, 60)
        horizon_days = fc2.slider("Forecast horizon (days)", 7, 180, 90)

        if st.button("📅 Run Forecast", type="primary"):
            today = date.today()
            history_start = (today - timedelta(days=lookback_days)).isoformat()
            history_end = (today + timedelta(days=1)).isoformat()

            log_box = st.empty()
            log_lines = []

            def _progress(label, count):
                log_lines.append(f"{label}: {count} historical scene(s)")
                log_box.code("\n".join(log_lines))

            with st.spinner("Gathering acquisition history..."):
                history_df, footprints = sat_forecast.gather_history(
                    st.session_state["aoi_geometry"], history_start, history_end, progress_cb=_progress
                )
            forecast_df = sat_forecast.build_forecast(history_df, today, horizon_days)
            st.session_state["history_df"] = history_df
            st.session_state["history_footprints"] = footprints
            st.session_state["forecast_df"] = forecast_df
            st.success(f"{len(forecast_df)} predicted overpass(es) through {today + timedelta(days=horizon_days)}.")

        forecast_df = st.session_state["forecast_df"]
        if isinstance(forecast_df, pd.DataFrame) and not forecast_df.empty:
            st.divider()
            tbl_tab, chart_tab, map_tab = st.tabs(["Table", "Timeline", "Recent footprints"])

            with tbl_tab:
                st.dataframe(forecast_df, use_container_width=True, height=350)
                csv_bytes = forecast_df.to_csv(index=False).encode("utf-8")
                st.download_button("⬇️ Download forecast CSV", csv_bytes, f"{aoi_name}_overpass_forecast.csv", "text/csv")

            with chart_tab:
                fig = px.scatter(
                    forecast_df, x="predicted_datetime_utc", y="platform", color="platform",
                    color_discrete_map=sat_forecast.PLATFORM_COLORS, hover_data=["basis", "days_until"],
                    title="Predicted overpasses",
                )
                fig.update_traces(marker=dict(size=12, symbol="line-ns-open", line=dict(width=2)))
                fig.update_layout(height=450, showlegend=False)
                st.plotly_chart(fig, use_container_width=True)

            with map_tab:
                history_df = st.session_state["history_df"]
                footprints = st.session_state["history_footprints"]
                center = st.session_state["aoi_geometry"].centroid(1).coordinates().getInfo()[::-1]
                fmap = esri_map(center, 10)
                folium.GeoJson(st.session_state["aoi_geometry"].getInfo(), name="AOI",
                                style_function=outline_style("#ef4444")).add_to(fmap)
                for platform, color in sat_forecast.PLATFORM_COLORS.items():
                    subset = history_df[history_df["platform"] == platform] if history_df is not None else pd.DataFrame()
                    if subset.empty:
                        continue
                    group = folium.FeatureGroup(name=f"{platform} ({len(subset)})")
                    for _, row in subset.iterrows():
                        fp = footprints.get((platform, row["id"]))
                        if fp:
                            folium.GeoJson(fp, style_function=outline_style(color), tooltip=row["id"]).add_to(group)
                    group.add_to(fmap)
                folium.LayerControl().add_to(fmap)
                st_folium(fmap, key="forecast_map", width=None, height=500)

# ============================================================ 5. LIVE TRACKER
with tab_orbit:
    st.header("Live Orbit Tracker")
    st.caption("Real-time satellite positions from CelesTrak TLEs, propagated with skyfield. No Earth Engine needed.")
    guide_expander("orbit")

    aoi_lat, aoi_lon = None, None
    geojson_path = Path(output_dir) / f"{aoi_name}.geojson"
    if geojson_path.exists():
        aoi_geojson = json.loads(geojson_path.read_text())
        ring = aoi_geojson["features"][0]["geometry"]["coordinates"][0]
        aoi_lon = sum(c[0] for c in ring) / len(ring)
        aoi_lat = sum(c[1] for c in ring) / len(ring)

    if aoi_lat is None:
        st.warning("Select an AOI in the **AOI** tab first.")
    else:
        forecast_days = st.slider("Physics-based forecast horizon (days)", 7, 60, 30)

        if st.button("🛰️ Refresh Positions", type="primary"):
            with st.spinner("Fetching live TLEs from CelesTrak..."):
                ts, satellites = sat_orbit.load_tles()
                t_now, snapshot_df = sat_orbit.snapshot(satellites, ts, aoi_lat, aoi_lon)
                orbit_forecast_df = sat_orbit.orbital_forecast(satellites, ts, t_now, aoi_lat, aoi_lon, forecast_days)
            st.session_state["orbit_ts"] = ts
            st.session_state["orbit_sats"] = satellites
            st.session_state["orbit_snapshot"] = snapshot_df
            st.session_state["orbit_time"] = t_now
            st.session_state["orbit_forecast_df"] = orbit_forecast_df
            st.success(f"Loaded {len(satellites)} satellite(s) — snapshot at {t_now.utc_iso()}")

        if st.session_state["orbit_snapshot"] is not None:
            st.divider()
            map_tab, table_tab, forecast_tab = st.tabs(["Live Map", "Current Positions", "Physics-based Forecast"])

            with map_tab:
                # OpenStreetMap needs no API key; CartoDB's tiles now watermark without one.
                fmap = folium.Map(location=[aoi_lat, aoi_lon], zoom_start=3, tiles="OpenStreetMap")
                geojson_data = json.loads(geojson_path.read_text())
                ring = geojson_data["features"][0]["geometry"]["coordinates"][0]
                folium.Polygon(
                    locations=[(c[1], c[0]) for c in ring], color="#ef4444", weight=3,
                    fill=True, fill_opacity=0.15, tooltip="AOI",
                ).add_to(fmap)

                ts = st.session_state["orbit_ts"]
                t_now = st.session_state["orbit_time"]
                snapshot_df = st.session_state["orbit_snapshot"]
                for name, sat in st.session_state["orbit_sats"].items():
                    color = sat_orbit.PLATFORM_COLORS.get(name, "#3388ff")
                    group = folium.FeatureGroup(name=name)
                    for segment in sat_orbit.ground_track(sat, ts, t_now):
                        folium.PolyLine(segment, color=color, weight=2, opacity=0.7).add_to(group)
                    now_row = snapshot_df[snapshot_df["satellite"] == name].iloc[0]
                    folium.CircleMarker(
                        location=(now_row["lat"], now_row["lon"]), radius=6, color=color, fill=True, fill_opacity=1,
                        tooltip=f"{name} — {now_row['distance_from_aoi_km']:.0f} km from AOI",
                    ).add_to(group)
                    group.add_to(fmap)
                folium.LayerControl().add_to(fmap)
                st_folium(fmap, key="orbit_map", width=None, height=550)

            with table_tab:
                st.dataframe(st.session_state["orbit_snapshot"], use_container_width=True, height=300)

            with forecast_tab:
                ofc = st.session_state["orbit_forecast_df"]
                st.dataframe(ofc, use_container_width=True, height=300)
                if not ofc.empty:
                    fig = px.scatter(
                        ofc, x="predicted_datetime_utc", y="satellite", color="satellite",
                        color_discrete_map=sat_orbit.PLATFORM_COLORS, size="closest_approach_km",
                        title="Physics-based predicted overpasses (smaller/closer = better pass)",
                    )
                    fig.update_layout(height=400, showlegend=False)
                    st.plotly_chart(fig, use_container_width=True)
                csv_bytes = ofc.to_csv(index=False).encode("utf-8")
                st.download_button("⬇️ Download orbital forecast CSV", csv_bytes, f"{aoi_name}_orbital_overpass_forecast.csv", "text/csv")

# =================================================================== 6. GITHUB
with tab_github:
    st.header("Push to GitHub")
    st.caption(
        "Creates (if needed) a private GitHub repo and pushes this project. "
        "downloads/ is never pushed — a manifest of file names/sizes is committed instead."
    )
    guide_expander("github")

    gc1, gc2 = st.columns(2)
    gh_user = gc1.text_input("GitHub username", value="")
    gh_repo = gc2.text_input("Repository name", value="satellite-data-search")
    gh_private = st.checkbox("Private repository", value=True)
    gh_token = st.text_input(
        "Personal Access Token", type="password",
        help="GitHub removed password-based git push in 2021 — create a classic token with `repo` scope at "
             "https://github.com/settings/tokens. Held only in memory for this run.",
    ).strip()

    if st.button("🔗 Push Now", type="primary", disabled=not (gh_user and gh_repo and gh_token)):
        log = st.empty()
        lines = []

        def log_line(msg):
            lines.append(msg)
            log.code("\n".join(lines))

        def run(cmd, redact=None):
            result = subprocess.run(cmd, capture_output=True, text=True)
            out, err = result.stdout, result.stderr
            if redact:
                out, err = out.replace(redact, "***"), err.replace(redact, "***")
            if result.returncode != 0:
                raise RuntimeError(f"git command failed (exit {result.returncode}):\n{err or out}")
            return out.strip()

        try:
            # manifest (no data, just names/sizes)
            manifest_path = Path("downloads_manifest.txt")
            dl = Path(download_dir)
            manifest_lines = []
            if dl.exists():
                for f in sorted(dl.rglob("*")):
                    if f.is_file():
                        manifest_lines.append(f"{f.relative_to(dl).as_posix()}\t{f.stat().st_size / (1024 ** 2):,.1f} MB")
            manifest_path.write_text("\n".join(manifest_lines) + ("\n" if manifest_lines else ""), encoding="utf-8")
            log_line(f"Recorded {len(manifest_lines)} downloaded file name(s) in downloads_manifest.txt")

            gi = Path(".gitignore")
            required = ["downloads/", "__pycache__/", "*.pyc", ".ipynb_checkpoints/", "*.bak"]
            existing = gi.read_text(encoding="utf-8").splitlines() if gi.exists() else []
            missing = [l for l in required if l not in existing]
            if missing:
                with open(gi, "a", encoding="utf-8") as f:
                    if existing and existing[-1] != "":
                        f.write("\n")
                    f.write("\n".join(missing) + "\n")
            log_line(".gitignore up to date")

            if not Path(".git").exists():
                run(["git", "init"])
                run(["git", "branch", "-M", "main"])
                log_line("Initialized git repository")

            import requests as _requests
            headers = {"Authorization": f"Bearer {gh_token}", "Accept": "application/vnd.github+json"}
            resp = _requests.get(f"https://api.github.com/repos/{gh_user}/{gh_repo}", headers=headers, timeout=30)
            if resp.status_code == 200:
                log_line(f"Repo {gh_user}/{gh_repo} already exists.")
            elif resp.status_code == 404:
                create_resp = _requests.post(
                    "https://api.github.com/user/repos", headers=headers,
                    json={"name": gh_repo, "private": gh_private}, timeout=30,
                )
                create_resp.raise_for_status()
                log_line(f"Created {'private' if gh_private else 'public'} repo: {create_resp.json()['html_url']}")
            else:
                resp.raise_for_status()

            run(["git", "add", "-A"])
            status = run(["git", "status", "--porcelain"])
            if status:
                message = f"Update {datetime.now().strftime('%Y-%m-%d %H:%M')}"
                run(["git", "commit", "-m", message])
                log_line(f"Committed: {message}")
            else:
                log_line("No changes to commit.")

            if "origin" not in run(["git", "remote"]).splitlines():
                run(["git", "remote", "add", "origin", f"https://github.com/{gh_user}/{gh_repo}.git"])

            push_url = f"https://{gh_token}@github.com/{gh_user}/{gh_repo}.git"
            run(["git", "push", push_url, "HEAD:main"], redact=gh_token)
            log_line(f"Pushed to https://github.com/{gh_user}/{gh_repo}")
            st.success("Push complete.")
        except Exception as e:
            st.error(str(e))

# ==================================================================== 7. HELP
with tab_help:
    st.header("Help & Guides")
    st.write(
        "A short PDF for every step — what it does, common gotchas, and what to do when something "
        "returns nothing or throws an error. New to this toolkit? Start with **Getting Started**: it "
        "walks through creating your own Earth Engine, Earthdata, and (optionally) GitHub accounts from "
        "scratch, so everything below actually connects for you."
    )
    st.divider()

    order = ["getting_started", "troubleshooting", "aoi", "search", "download", "forecast", "orbit", "github"]
    for key in order:
        filename, title, blurb = GUIDES[key]
        path = GUIDES_DIR / filename
        c1, c2 = st.columns([5, 1])
        with c1:
            st.markdown(f"**{title}**")
            st.caption(blurb)
        with c2:
            if path.exists():
                st.download_button("⬇️ PDF", path.read_bytes(), filename, "application/pdf", key=f"help_dl_{key}")
            else:
                st.caption("missing")
        st.divider()
