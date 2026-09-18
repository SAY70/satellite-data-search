"""Generates the flow diagrams used in README.md — one per pipeline step,
plus a banner and an overview. Content lives here as plain data; run this
script to regenerate docs/images/*.svg after editing anything below.

Usage:  python docs/generate_diagrams.py
"""

from pathlib import Path

OUT_DIR = Path(__file__).parent / "images"
OUT_DIR.mkdir(exist_ok=True)

FONT = "'Segoe UI', Helvetica, Arial, sans-serif"
INK = "#1e293b"
SUBINK = "#64748b"
LINE = "#94a3b8"
CARD_BG = "#ffffff"
PAGE_BG = "#f8fafc"


def _esc(s):
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _wrap_text(x, y, s, size, weight, color, anchor="middle", max_chars=24, line_height=None):
    """Very simple word-wrap for SVG <text>: splits into <tspan> lines."""
    line_height = line_height or size + 4
    words = s.split()
    lines, current = [], ""
    for w in words:
        trial = (current + " " + w).strip()
        if len(trial) > max_chars and current:
            lines.append(current)
            current = w
        else:
            current = trial
    if current:
        lines.append(current)
    start_y = y - (len(lines) - 1) * line_height / 2
    tspans = "".join(
        f'<tspan x="{x}" y="{start_y + i * line_height:.1f}">{_esc(line)}</tspan>' for i, line in enumerate(lines)
    )
    return f'<text font-family="{FONT}" font-size="{size}" font-weight="{weight}" fill="{color}" text-anchor="{anchor}">{tspans}</text>'


def _box(x, y, w, h, fill, stroke, rx=14):
    return f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{rx}" fill="{fill}" stroke="{stroke}" stroke-width="1.6"/>'


def _arrow(x1, y1, x2, y2, color=LINE):
    return f'<line x1="{x1:.1f}" y1="{y1:.1f}" x2="{x2:.1f}" y2="{y2:.1f}" stroke="{color}" stroke-width="2" marker-end="url(#arrow)"/>'


def flow_diagram(filename, title, columns, accent="#0f766e", box_w=220, box_h=92, col_gap=76, row_gap=22, margin=34):
    """columns: list of columns; each column is a list of (icon, label, sublabel) boxes.
    Adjacent columns are connected fully (every box in col i -> every box in col i+1)."""
    n_cols = len(columns)
    max_rows = max(len(c) for c in columns)
    title_h = 46 if title else 0

    content_h = max_rows * box_h + (max_rows - 1) * row_gap
    width = margin * 2 + n_cols * box_w + (n_cols - 1) * col_gap
    height = margin * 2 + title_h + content_h

    # compute box positions
    positions = []  # positions[col_idx] = list of (x, y, w, h)
    for i, col in enumerate(columns):
        n = len(col)
        col_h = n * box_h + (n - 1) * row_gap
        y0 = margin + title_h + (content_h - col_h) / 2
        x = margin + i * (box_w + col_gap)
        col_positions = [(x, y0 + j * (box_h + row_gap), box_w, box_h) for j in range(n)]
        positions.append(col_positions)

    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
        f'viewBox="0 0 {width} {height}">',
        f'<rect width="{width}" height="{height}" fill="{PAGE_BG}"/>',
        '<defs><marker id="arrow" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" '
        f'orient="auto-start-reverse"><path d="M0,0 L10,5 L0,10 z" fill="{LINE}"/></marker></defs>',
    ]
    if title:
        parts.append(_wrap_text(width / 2, margin + 22, title, 19, "700", INK, max_chars=90))

    # arrows first (so boxes sit on top)
    for i in range(n_cols - 1):
        for (x1, y1, w1, h1) in positions[i]:
            for (x2, y2, w2, h2) in positions[i + 1]:
                parts.append(_arrow(x1 + w1, y1 + h1 / 2, x2, y2 + h2 / 2))

    # boxes
    for col, col_pos in zip(columns, positions):
        for (icon, label, sub), (x, y, w, h) in zip(col, col_pos):
            parts.append(_box(x, y, w, h, CARD_BG, accent))
            parts.append(_wrap_text(x + w / 2, y + (30 if sub else h / 2 - 4), f"{icon}  {label}", 15, "700", INK, max_chars=22))
            if sub:
                parts.append(_wrap_text(x + w / 2, y + h - 22, sub, 11.5, "500", SUBINK, max_chars=30))

    parts.append("</svg>")
    (OUT_DIR / filename).write_text("\n".join(parts), encoding="utf-8")
    print(f"Wrote {OUT_DIR / filename}  ({width}x{height})")


def banner(filename="banner.svg"):
    width, height = 1200, 220
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
        '<defs><linearGradient id="bg" x1="0" y1="0" x2="1" y2="1">'
        '<stop offset="0%" stop-color="#0f766e"/><stop offset="100%" stop-color="#134e4a"/>'
        "</linearGradient></defs>",
        f'<rect width="{width}" height="{height}" rx="18" fill="url(#bg)"/>',
        # Size chosen so the full title fits inside the 1200px banner without clipping.
        f'<text x="{width/2}" y="96" font-family="{FONT}" font-size="33" font-weight="800" '
        f'fill="#ffffff" text-anchor="middle">🛰️ Satellite Data Search and Overpass Forecast Toolkit</text>',
        f'<text x="{width/2}" y="140" font-family="{FONT}" font-size="17" font-weight="500" '
        f'fill="#99f6e4" text-anchor="middle">Find &#183; review &#183; download &#183; forecast &#183; track</text>',
        f'<text x="{width/2}" y="172" font-family="{FONT}" font-size="14.5" font-weight="500" '
        f'fill="#5eead4" text-anchor="middle">Sentinel-1 &#183; Sentinel-2 &#183; Landsat 8/9 &#183; NISAR &#183; MODIS &#183; Sentinel-6</text>',
        "</svg>",
    ]
    (OUT_DIR / filename).write_text("\n".join(parts), encoding="utf-8")
    print(f"Wrote {OUT_DIR / filename}  ({width}x{height})")


banner()

flow_diagram(
    "pipeline_overview.svg",
    "The pipeline — six stages, one shared codebase",
    columns=[
        [("🗺️", "1. AOI", "Draw & export")],
        [("🔍", "2. Search", "6 sensors, EE + CMR")],
        [("⬇️", "3. Download", "Clip or archive")],
        [("📅", "4. Forecast", "Real revisit patterns")],
        [("🛰️", "5. Live Tracker", "TLE orbit physics")],
        [("🔗", "6. GitHub", "Back up your work")],
    ],
    accent="#0f766e",
    box_w=178,
)

flow_diagram(
    "step1_aoi.svg",
    "Step 1 — AOI Selection",
    columns=[
        [("🖊️", "Draw on map", "Rectangle or polygon")],
        [("💾", "export_all()", "aoi_export.py")],
        [
            ("📄", ".geojson", "read by every later step"),
            ("🌍", ".kml", "open in Google Earth"),
            ("🗜️", ".kmz", "compressed KML"),
        ],
    ],
    accent="#ef4444",
)

flow_diagram(
    "step2_search.svg",
    "Step 2 — Multi-Mission Search",
    columns=[
        [("🗺️", "Your AOI", "+ date range")],
        [
            ("🌐", "Google Earth Engine", "S2, Landsat, MODIS"),
            ("🛰️", "NASA CMR archive", "S1, NISAR, S6, HLS"),
        ],
        [("📊", "Combined table", "filter by coverage/cloud")],
    ],
    accent="#eab308",
)

flow_diagram(
    "step3_download.svg",
    "Step 3 — Download Filtered Scenes",
    columns=[
        [("📊", "Filtered scenes", "scene_search.csv")],
        [
            ("🌐", "Earth Engine source", "clipped to AOI, small"),
            ("🛰️", "CMR source", "full file, needs Earthdata login"),
        ],
        [("💾", "downloads/", "one folder per product")],
    ],
    accent="#f97316",
)

flow_diagram(
    "step4_forecast.svg",
    "Step 4 — Future Overpass Forecast",
    columns=[
        [("🕓", "Last ~60 days", "real acquisition dates")],
        [("🔎", "Detect gap pattern", "e.g. [6, 13]-day repeat")],
        [("📅", "Project forward", "predicted future passes")],
    ],
    accent="#a855f7",
)

flow_diagram(
    "step5_orbit.svg",
    "Step 5 — Live Orbit Tracker",
    columns=[
        [("📡", "CelesTrak", "live TLE orbital elements")],
        [("🧮", "skyfield", "propagate orbit forward")],
        [("🛰️", "Ground track", "vs. your AOI, in real time")],
    ],
    accent="#0ea5e9",
)

flow_diagram(
    "step6_github.svg",
    "Step 6 — Push to GitHub",
    columns=[
        [("💻", "Local commit", "git add + commit")],
        [("🔎", "Check/create repo", "GitHub REST API")],
        [("🔑", "git push", "token, never saved to disk")],
        [("🔒", "Private repo", "yours, on GitHub")],
    ],
    accent="#ec4899",
    box_w=190,
)

print("\nAll diagrams generated.")
