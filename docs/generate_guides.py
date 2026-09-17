"""Generates the PDF guides shown in the dashboard's Help tab / per-step
expanders. Content lives here as plain data; run this script to regenerate
docs/pdf/*.pdf after editing anything below.

Usage:  python docs/generate_guides.py
"""

from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.colors import HexColor
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import LETTER
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import (
    HRFlowable,
    ListFlowable,
    ListItem,
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

OUT_DIR = Path(__file__).parent / "pdf"
OUT_DIR.mkdir(exist_ok=True)

TEAL = HexColor("#0f766e")
DARK = HexColor("#1e293b")
GRAY = HexColor("#475569")
LIGHT_BG = HexColor("#f1f5f9")
WARN_BG = HexColor("#fef3c7")
WARN_TEXT = HexColor("#92400e")
TIP_BG = HexColor("#dbeafe")
TIP_TEXT = HexColor("#1e40af")

base = getSampleStyleSheet()
STYLES = {
    "title": ParagraphStyle("GuideTitle", parent=base["Title"], fontSize=24, textColor=TEAL,
                             spaceAfter=4, alignment=TA_LEFT),
    "subtitle": ParagraphStyle("GuideSubtitle", parent=base["Normal"], fontSize=12, textColor=GRAY,
                                spaceAfter=18),
    "h2": ParagraphStyle("H2", parent=base["Heading2"], fontSize=15, textColor=DARK,
                          spaceBefore=16, spaceAfter=8),
    "body": ParagraphStyle("Body", parent=base["Normal"], fontSize=10.5, textColor=DARK,
                            leading=15, spaceAfter=8),
    "bullet": ParagraphStyle("Bullet", parent=base["Normal"], fontSize=10.5, textColor=DARK, leading=15),
    "code": ParagraphStyle("Code", parent=base["Code"], fontSize=9.5, textColor=DARK,
                            backColor=LIGHT_BG, borderPadding=6, leading=13),
    "tip": ParagraphStyle("Tip", parent=base["Normal"], fontSize=10, textColor=TIP_TEXT,
                           backColor=TIP_BG, borderPadding=8, leading=14),
    "warn": ParagraphStyle("Warn", parent=base["Normal"], fontSize=10, textColor=WARN_TEXT,
                            backColor=WARN_BG, borderPadding=8, leading=14),
}


def build_pdf(filename, title, subtitle, blocks):
    doc = SimpleDocTemplate(
        str(OUT_DIR / filename), pagesize=LETTER,
        topMargin=0.75 * inch, bottomMargin=0.75 * inch,
        leftMargin=0.85 * inch, rightMargin=0.85 * inch,
        title=title,
    )
    story = [
        Paragraph("🛰️ Satellite Data Search Toolkit", STYLES["subtitle"]),
        Paragraph(title, STYLES["title"]),
        Paragraph(subtitle, STYLES["subtitle"]),
        HRFlowable(width="100%", thickness=1, color=TEAL, spaceAfter=14),
    ]
    for block in blocks:
        kind = block[0]
        if kind == "h2":
            story.append(Paragraph(block[1], STYLES["h2"]))
        elif kind == "p":
            story.append(Paragraph(block[1], STYLES["body"]))
        elif kind == "bullet":
            items = [ListItem(Paragraph(t, STYLES["bullet"]), leftIndent=6) for t in block[1]]
            story.append(ListFlowable(items, bulletType="bullet", leftIndent=16, spaceAfter=8))
        elif kind == "numbered":
            items = [ListItem(Paragraph(t, STYLES["bullet"]), leftIndent=6) for t in block[1]]
            story.append(ListFlowable(items, bulletType="1", leftIndent=18, spaceAfter=8))
        elif kind == "code":
            story.append(Paragraph(block[1].replace("\n", "<br/>"), STYLES["code"]))
            story.append(Spacer(1, 8))
        elif kind == "tip":
            story.append(Paragraph(f"<b>💡 Tip —</b> {block[1]}", STYLES["tip"]))
            story.append(Spacer(1, 8))
        elif kind == "warn":
            story.append(Paragraph(f"<b>⚠️ Watch out —</b> {block[1]}", STYLES["warn"]))
            story.append(Spacer(1, 8))
        elif kind == "table":
            headers, rows = block[1], block[2]
            data = [[Paragraph(f"<b>{h}</b>", STYLES["bullet"]) for h in headers]]
            for row in rows:
                data.append([Paragraph(str(c), STYLES["bullet"]) for c in row])
            t = Table(data, hAlign="LEFT", colWidths=block[3] if len(block) > 3 else None)
            t.setStyle(TableStyle([
                ("BACKGROUND", (0, 0), (-1, 0), TEAL),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#cbd5e1")),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, LIGHT_BG]),
                ("TOPPADDING", (0, 0), (-1, -1), 5),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
                ("LEFTPADDING", (0, 0), (-1, -1), 6),
            ]))
            story.append(t)
            story.append(Spacer(1, 10))
        elif kind == "spacer":
            story.append(Spacer(1, block[1]))
        elif kind == "pagebreak":
            story.append(PageBreak())
    doc.build(story)
    print(f"Wrote {OUT_DIR / filename}")


# --------------------------------------------------------------- content ---

GUIDES = []


def guide(filename, title, subtitle, blocks):
    GUIDES.append((filename, title, subtitle, blocks))


guide(
    "00_Getting_Started.pdf",
    "Getting Started",
    "Set up your own accounts and connect the toolkit — a one-time process, about 10 minutes.",
    [
        ("p", "This toolkit finds, reviews, and downloads satellite imagery over an area you draw, "
              "and helps you plan field visits around future satellite passes. It uses three outside "
              "services, each needing its own free account: <b>Google Earth Engine</b> (imagery search), "
              "<b>NASA Earthdata</b> (real archive downloads), and optionally <b>GitHub</b> (to back up "
              "your project). None of this costs money for normal personal/research use."),
        ("warn", "The <b>Earth Engine project ID</b> already filled into the notebooks and app "
                 "(<font face='Courier'>rosy-precinct-498822-e1</font>) belongs to this toolkit's original "
                 "author. It will <b>not</b> work for you — Earth Engine projects are tied to one Google "
                 "account. You must create your own and replace that value everywhere before anything "
                 "connects to Earth Engine."),

        ("h2", "Step 1 — Install Python packages"),
        ("p", "From the project folder, install everything the toolkit needs:"),
        ("code", "pip install -r requirements.txt"),

        ("h2", "Step 2 — Create your own Earth Engine project"),
        ("numbered", [
            "Go to <font face='Courier'>code.earthengine.google.com/register</font> and sign in with "
            "any Google account.",
            "Choose <b>\"Unpaid usage\"</b> (free, for research/personal/education) unless you specifically "
            "need a commercial license.",
            "When asked for a Cloud project, either create a new one or pick an existing Google Cloud "
            "project — write down its <b>Project ID</b> (a short lowercase-hyphenated string like "
            "<font face='Courier'>my-name-12345</font>, shown under the project's display name — not the "
            "display name itself).",
            "Registration automatically enables the Earth Engine API on that project — no separate step "
            "needed.",
        ]),
        ("tip", "Free Google accounts (Gmail) work fine. You do not need a company or paid Google Cloud "
                "billing account for normal-sized research use."),

        ("h2", "Step 3 — Point the toolkit at your project"),
        ("p", "Replace the project ID everywhere it appears with your own:"),
        ("bullet", [
            "In every notebook (<font face='Courier'>1_AOI_Selection.ipynb</font> through "
            "<font face='Courier'>4_Future_Overpass_Forecast.ipynb</font>): find the line "
            "<font face='Courier'>EE_PROJECT = \"...\"</font> near the top and put your Project ID "
            "between the quotes.",
            "In the dashboard app: type your Project ID into the <b>\"Earth Engine project\"</b> box in "
            "the sidebar before clicking Connect.",
        ]),

        ("h2", "Step 4 — Sign in (no code to copy/paste)"),
        ("p", "Run the setup cell in any notebook, or click <b>\"Connect to Earth Engine\"</b> in the "
              "app's sidebar. The first time, your browser opens to a Google sign-in page:"),
        ("numbered", [
            "Sign in with the same Google account you registered in Step 2.",
            "Click <b>Allow</b> on the permissions screen.",
            "The browser tab shows a success message — switch back to your notebook/app, it finishes "
              "automatically. Nothing to copy or type.",
        ]),
        ("tip", "This only happens once per computer. After the first successful sign-in, a credential "
                "file is cached and every future run just connects instantly."),

        ("h2", "Step 5 — NASA Earthdata Login (only needed for Download)"),
        ("p", "Some products (Sentinel-1, NISAR, Sentinel-6, and the HLS harmonized products) come from "
              "NASA's real data archive rather than Earth Engine, and downloading them needs a free "
              "Earthdata account:"),
        ("numbered", [
            "Register at <font face='Courier'>urs.earthdata.nasa.gov</font> (free, a few minutes).",
            "You'll enter this username/password directly in the Download step when you're ready to "
              "download — it's never saved to a file.",
        ]),
        ("p", "See the <b>Download Guide</b> for a note on one extra one-time step ASF DAAC requires "
              "(authorizing an application) before Sentinel-1/NISAR downloads work."),

        ("h2", "Step 6 — (Optional) GitHub, for backing up your project"),
        ("p", "Only needed if you want to push your project to your own private GitHub repository — "
              "see the <b>GitHub Sync Guide</b> for the full walkthrough (you'll need a free GitHub "
              "account and a Personal Access Token, not your GitHub password)."),

        ("h2", "Step 7 — Run it"),
        ("p", "Two ways to use the toolkit, both use the exact same underlying code:"),
        ("bullet", [
            "<b>All-in-one dashboard</b> (recommended for first-time use): run "
            "<font face='Courier'>streamlit run app.py</font> and open the link it prints "
            "(usually <font face='Courier'>http://localhost:8501</font>).",
            "<b>Notebooks</b>: open <font face='Courier'>1_AOI_Selection.ipynb</font> and run the cells "
            "top to bottom, then <font face='Courier'>2_Sentinel_Search.ipynb</font>, and so on in order.",
        ]),
        ("tip", "Stuck on a specific step? Each stage has its own short guide — open the Help tab in the "
                "dashboard, or the matching PDF in <font face='Courier'>docs/pdf/</font>."),
    ],
)

guide(
    "01_AOI_Selection_Guide.pdf",
    "Step 1: Area of Interest (AOI)",
    "Draw the place you care about — everything downstream is scoped to this shape.",
    [
        ("p", "Your AOI (Area of Interest) is the polygon or rectangle that defines the region the whole "
              "toolkit searches, filters, and downloads imagery for. You draw it once and it's reused by "
              "every later step."),
        ("h2", "How to draw one"),
        ("numbered", [
            "Use the rectangle or polygon tool on the map (top-left drawing toolbar).",
            "Draw exactly <b>one</b> shape over your area. If you draw more than one, only the last shape "
              "is used.",
            "Click <b>Save as AOI</b> (dashboard) or run the export cell (notebook).",
        ]),
        ("h2", "Sizing your AOI"),
        ("bullet", [
            "Keep it reasonably small (a farm field, a watershed, a small county) — the search step "
              "queries every scene that even partially overlaps your AOI, so a very large AOI (a whole "
              "state or country) means far more results and much slower searches.",
            "Very small AOIs (a few hundred meters across) are fine and often ideal for field-scale work.",
        ]),
        ("h2", "What gets created"),
        ("p", "Saving writes three files with the same shape, for different uses:"),
        ("table", ["File", "Use"], [
            [".geojson", "Read by every other step in this toolkit"],
            [".kml", "Open in Google Earth"],
            [".kmz", "Compressed KML, smaller file size"],
        ]),
        ("warn", "If you redraw and re-save with the same AOI name, it silently overwrites the previous "
                 "files. Use a different <font face='Courier'>AOI_NAME</font> if you want to keep more "
                 "than one area side by side."),
    ],
)

guide(
    "02_Search_Guide.pdf",
    "Step 2: Multi-Mission Search",
    "Find every available scene from six satellite missions over your AOI and date range.",
    [
        ("p", "This step searches Sentinel-1, Sentinel-2, Landsat 8/9, NISAR, MODIS, and Sentinel-6 for "
              "your AOI and date range, pulling each from wherever it actually lives — Google Earth "
              "Engine for what's in its catalog, and each mission's real NASA archive for what isn't."),
        ("h2", "Picking a date range"),
        ("p", "Start with something generous (60–90 days) — narrow it down once you see how many scenes "
              "come back. A very short window can easily return zero results for tasked/less-frequent "
              "sensors even though data exists just outside your window."),
        ("h2", "Why a sensor might show zero results"),
        ("table", ["Sensor", "Common reason for 0 results"], [
            ["Sentinel-1", "Acquisition is tasked by ESA, not automatic — your AOI may simply not be in "
                           "the current observation plan for that date range"],
            ["Sentinel-6", "Ocean-only altimetry mission — always 0 for a land AOI, this is correct"],
            ["NISAR", "Still in early commissioning phase with limited coverage as of this writing"],
        ], [1.4 * inch, 4.3 * inch]),
        ("p", "None of these are bugs — they reflect what each mission actually collected. Widen the date "
              "range or check the Live Tracker step for an independent, orbit-physics-based cross-check."),
        ("h2", "Filtering results"),
        ("bullet", [
            "<b>Minimum AOI coverage %</b> — drop scenes that only clip a corner of your AOI.",
            "<b>Maximum cloud cover %</b> — only applies to optical sensors (Sentinel-2, Landsat); radar "
              "(Sentinel-1, NISAR) and MODIS rows pass through regardless, since cloud cover doesn't "
              "block them the same way.",
        ]),
        ("tip", "Save the filtered CSV before moving to the Download step — that CSV is what the "
                "download step actually reads."),
    ],
)

guide(
    "03_Download_Guide.pdf",
    "Step 3: Download Filtered Scenes",
    "Pull the scenes you kept — from Earth Engine (clipped, small) or the real archive (full files).",
    [
        ("p", "Downloads use two different mechanisms depending on where a product actually lives:"),
        ("table", ["Source", "Products", "What you get"], [
            ["Earth Engine", "Sentinel-2 L2A/L1C, Landsat 8/9, MODIS", "Clipped to your AOI — small, "
                                                                        "no login needed"],
            ["Real archive (CMR)", "Sentinel-1, NISAR, Sentinel-6, HLS", "Full original files — can be "
                                                                          "large, needs Earthdata login"],
        ], [1.3 * inch, 2.1 * inch, 2.3 * inch]),
        ("h2", "One-time ASF DAAC authorization"),
        ("p", "The first time you download Sentinel-1 or NISAR data, ASF DAAC may reject your Earthdata "
              "credentials even though they're correct, until you authorize their specific application:"),
        ("numbered", [
            "Go to <font face='Courier'>urs.earthdata.nasa.gov/profile/edit_applications</font> while "
              "logged in.",
            "Under \"Authorized Apps,\" search for and approve <b>\"Alaska Satellite Facility Data "
              "Access\"</b> (and similar ASF-related entries if prompted).",
            "Retry the download — it should now authenticate successfully.",
        ]),
        ("h2", "Before you click download"),
        ("bullet", [
            "Check the per-sensor size totals shown before downloading — <b>NISAR RSLC files run "
              "~25 GB each</b>, by far the largest product this toolkit handles.",
            "You can select individual sensors to download rather than everything at once — skip the "
              "huge ones if you don't need them.",
            "Downloads resume safely: a file that's already completed is skipped, and an interrupted "
              "download never gets mistaken for a finished one on retry.",
        ]),
        ("warn", "Your Earthdata password is only held in memory for the run — it is never written to "
                 "disk or saved into a notebook file. You'll re-enter it each session."),
    ],
)

guide(
    "04_Forecast_Guide.pdf",
    "Step 4: Future Overpass Forecast",
    "Predict upcoming satellite passes from real recent acquisition patterns — not textbook assumptions.",
    [
        ("p", "Rather than assuming each satellite's textbook nominal revisit cycle (10 days for "
              "Sentinel-2, 16 for Landsat, etc.), this step looks at the last ~60 days of <i>actual</i> "
              "acquisitions over your specific AOI, detects the real repeating gap pattern, and projects "
              "it forward. Real patterns often differ from the nominal figure — for example, an AOI "
              "sitting in the overlap between two adjacent orbit paths gets imaged more often than the "
              "nominal cycle implies."),
        ("h2", "Reading the \"basis\" column"),
        ("bullet", [
            "<b>\"empirical pattern [...]\"</b> — a real repeating gap was detected in recent history; "
              "trust this.",
            "<b>\"nominal N-day cycle...\"</b> — not enough recent history to confirm a real pattern, so "
              "it fell back to the textbook figure; treat this as lower-confidence.",
        ]),
        ("h2", "Confidence by sensor"),
        ("bullet", [
            "<b>Sentinel-2, Landsat, NISAR</b> — acquired systematically over land on every overpass, so "
              "these predictions are reliable.",
            "<b>MODIS</b> — near-daily and systematic, so its forecast is basically \"tomorrow, and every "
              "day after\" — correct, but not a very selective planning signal by itself.",
            "<b>Sentinel-1</b> — acquisition is <i>tasked</i> by ESA, meaning the satellite flies over on "
              "schedule but whether it actually collects data for your AOI on a given pass is a separate "
              "decision this can't see. Treat these predictions cautiously, especially with a \"nominal\" "
              "basis.",
        ]),
        ("tip", "For an independent cross-check that doesn't rely on acquisition history at all, use the "
                "Live Tracker step — it predicts geometric overpasses directly from orbital mechanics."),
    ],
)

guide(
    "05_Live_Tracker_Guide.pdf",
    "Step 5: Live Orbit Tracker",
    "Real-time satellite positions and physics-based overpass predictions — no Earth Engine needed.",
    [
        ("p", "This step pulls each satellite's current real orbital elements (TLEs) from CelesTrak, a "
              "free public catalog, and propagates them forward using the same orbit-mechanics technique "
              "used by sites like N2YO. It needs no Earth Engine project and no login of any kind."),
        ("h2", "What it predicts, and what it doesn't"),
        ("p", "This predicts <b>when a satellite's swath geometrically crosses your AOI</b> — a necessary "
              "condition for an image, but not a guarantee one was taken:"),
        ("bullet", [
            "<b>Sentinel-2 and Landsat</b> acquire systematically on every qualifying pass, so these "
              "predictions are directly reliable.",
            "<b>Sentinel-1</b> is tasked — whether ESA actually collects an image on a geometrically "
              "valid pass is a separate planning decision this cannot see. Useful as a cross-check "
              "against the Forecast step, especially when that step has too little history for a "
              "confident pattern.",
        ]),
        ("h2", "Reading the map"),
        ("p", "\"Current position\" reflects the moment you clicked Refresh — it does not update live on "
              "its own; click Refresh again to get a new snapshot. Each satellite's ground track line "
              "spans roughly 20 minutes before to 100 minutes after that moment, so you can see which "
              "direction it's heading."),
        ("tip", "Swath widths used here are approximate nominal figures (Sentinel-1 IW ≈250 km, "
                "Sentinel-2 ≈290 km, Landsat ≈185 km) — real swaths vary slightly by acquisition mode."),
    ],
)

guide(
    "06_GitHub_Sync_Guide.pdf",
    "Step 6: Push to GitHub",
    "Back up your project to your own private GitHub repository.",
    [
        ("p", "This step commits and pushes your project (notebooks, code, small output files) to a "
              "private GitHub repository, creating it automatically the first time if it doesn't exist. "
              "It never pushes the <font face='Courier'>downloads/</font> folder — a text file listing "
              "every downloaded file's name and size is committed instead, so there's a record without "
              "the multi-gigabyte data."),
        ("h2", "You need a Personal Access Token, not your password"),
        ("p", "GitHub removed password-based Git access in 2021. You need a Personal Access Token (PAT) "
              "instead:"),
        ("numbered", [
            "Go to <font face='Courier'>github.com/settings/tokens</font> while signed in to your own "
              "GitHub account.",
            "Click <b>Generate new token</b> → <b>classic</b>.",
            "Give it any name, set an expiration you're comfortable with, and check the <b>repo</b> "
              "scope box.",
            "Click Generate, then copy the token immediately — GitHub only shows it once.",
            "Paste it into the token field when prompted. It's held only in memory for that run, never "
              "written to disk.",
        ]),
        ("h2", "If you get a 401 Unauthorized error"),
        ("p", "This means GitHub rejected the token itself — not a permissions problem. Common causes:"),
        ("bullet", [
            "The token expired or was revoked — generate a new one.",
            "A stray space or newline got pasted along with it — re-paste carefully.",
            "You entered your GitHub account password by mistake instead of a token — passwords no "
              "longer work here at all.",
        ]),
        ("tip", "Re-running the whole flow after fixing the token is always safe — it only creates the "
                "repo once and only commits when something actually changed."),
    ],
)


if __name__ == "__main__":
    for filename, title, subtitle, blocks in GUIDES:
        build_pdf(filename, title, subtitle, blocks)
    print(f"\n{len(GUIDES)} guide(s) written to {OUT_DIR}")
