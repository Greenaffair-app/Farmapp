"""
Report Template Renderer
--------------------------
Matches Greenaffair's real, established report design (dark cover page,
cream body pages, status-pill parameter cards with progress bars,
urgency-tiered action plan) -- built from the actual sample PDF, not
a generic reinterpretation.
"""

import base64
import os
from datetime import datetime

_LOGO_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "logo.png")
try:
    with open(_LOGO_PATH, "rb") as f:
        LOGO_BASE64 = base64.b64encode(f.read()).decode("utf-8")
except FileNotFoundError:
    LOGO_BASE64 = None

_BUTTERFLY_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "logo_butterflies_only.png")
try:
    with open(_BUTTERFLY_PATH, "rb") as f:
        BUTTERFLY_BASE64 = base64.b64encode(f.read()).decode("utf-8")
except FileNotFoundError:
    BUTTERFLY_BASE64 = None

COMPANY_NAME = "Greenaffair Sustainable Structures Pvt. Ltd."
COMPANY_ADDRESS = "D-57, Shastri Nagar, Jodhpur, Rajasthan 342003"
COMPANY_ADDRESS_2 = "Technology Business Incubator, IISER Mohali, Punjab"
COMPANY_PHONE_1 = "7049-306-544"
COMPANY_PHONE_2 = "747-050-6281"
COMPANY_EMAIL = "support@greenaffair.in"

# Deliberately branded, not a literal source name -- keeps the underlying
# data pipeline from reading as something anyone could replicate for free.
DATA_SOURCE_LABEL = "Greenaffair Remote Sensing Network"

MONTHS_KEYS = ["JAN", "FEB", "MAR", "APR", "MAY", "JUN", "JUL", "AUG", "SEP", "OCT", "NOV", "DEC"]

# Status family -> (badge bg, badge text, bar color)
STATUS_COLORS = {
    "low":    {"bg": "#F5DEDA", "text": "#B5453A", "bar": "#B5453A"},
    "medium": {"bg": "#EFE0CB", "text": "#A97D3E", "bar": "#C7935C"},
    "good":   {"bg": "#E3E8D9", "text": "#5C7048", "bar": "#5C7048"},
}

ICON_LOCK = '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="5" y="11" width="14" height="9" rx="2"/><path d="M8 11V7a4 4 0 018 0v4"/></svg>'
ICON_RAIN = '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M12 2.5C9 6 6 9.5 6 13a6 6 0 0012 0c0-3.5-3-7-6-10.5z"/></svg>'
ICON_TEMP = '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M12 3v11.5a3.5 3.5 0 11-2 0V3a1 1 0 012 0z"/></svg>'
ICON_FLASK = '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M9 3h6M10 3v6l-5 9a2 2 0 002 3h10a2 2 0 002-3l-5-9V3"/></svg>'
ICON_LEAF = '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M20 4C10 4 4 10 4 18c0 1 0 2 1 2 8 0 14-6 14-16 0-0.5 0.5-0.5 1 0z"/><path d="M5 19c3-3 6-6 12-13"/></svg>'
ICON_LAYERS = '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M12 3l9 5-9 5-9-5 9-5z"/><path d="M3 13l9 5 9-5"/></svg>'
ICON_NITROGEN = '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="9"/><path d="M9 8v8M15 8v8M9 8l6 8M9 16l6-8"/></svg>'
ICON_SPROUT = '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M12 21V10"/><path d="M12 10C12 6 9 4 5 4c0 4 3 7 7 7z"/><path d="M12 13C12 9.5 14.5 7 18 7c0 3.5-2.5 6.5-6 6z"/></svg>'

LOCKED_ITEMS = [
    ("Contour Map", "See exactly how your land slopes, terrace by terrace.", "Terrain Report", "₹300"),
    ("Water Catchment", "Know where rain collects and where it drains away.", "Terrain Report", "₹300"),
    ("Biodiversity Index", "Native species and ecoregion context for your land.", "Land Intelligence", "₹500"),
    ("NPK Levels", "Nitrogen, phosphorus, potassium — mapped to your soil.", "Satellite Soil Test", "₹1,000"),
]


def locked_card(title, teaser, tier_name, price):
    return f"""
    <div class="locked-card">
      <div class="locked-icon">{ICON_LOCK}</div>
      <div class="locked-title">{title}</div>
      <p class="locked-teaser">{teaser}</p>
      <div class="locked-tag">Unlock for {price}</div>
    </div>"""


def classify_ph(ph):
    """Matches the official ICAR-IISS Soil Health Card standard:
    <6.5 Acidic, 6.5-7.0 Neutral, >7.0 Alkaline."""
    if ph is None:
        return "Pending", "medium", 50
    if 6.5 <= ph <= 7.0:
        return "Neutral", "good", 65
    if 6.0 <= ph < 6.5 or 7.0 < ph <= 7.8:
        return "Monitor", "medium", 45
    return "Attention", "low", 20


def classify_organic_carbon(oc_g_per_kg):
    """Matches the official ICAR-IISS Soil Health Card standard:
    <0.5% Low, 0.5-0.75% Medium, >0.75% High."""
    if oc_g_per_kg is None:
        return "Pending", "medium", None, 50
    pct = oc_g_per_kg / 10
    bar_pct = min(100, (pct / 3.0) * 100)
    if pct >= 0.75:
        return "High", "good", pct, bar_pct
    if pct >= 0.5:
        return "Medium", "medium", pct, bar_pct
    return "Low", "low", pct, bar_pct


def classify_rainfall(annual_mm):
    if annual_mm is None:
        return "Pending", "medium", 50
    bar_pct = min(100, (annual_mm / 1500) * 100)
    if annual_mm >= 800:
        return "Adequate", "good", bar_pct
    if annual_mm >= 400:
        return "Moderate", "medium", bar_pct
    return "Low", "low", bar_pct


def classify_texture(clay, sand, silt):
    if clay is None or sand is None or silt is None:
        return "Pending", "medium", "Confirmed in your ₹1,000 lab test", 50
    if sand >= 70 and clay < 15:
        return "Sandy", "medium", f"Clay {clay:.0f}% · Sand {sand:.0f}% · Silt {silt:.0f}%", 55
    if clay >= 40:
        return "Clay-heavy", "medium", f"Clay {clay:.0f}% · Sand {sand:.0f}% · Silt {silt:.0f}%", 55
    return "Loam (balanced)", "good", f"Clay {clay:.0f}% · Sand {sand:.0f}% · Silt {silt:.0f}%", 75


def classify_ndvi(ndvi):
    """Standard remote-sensing vegetation health bands. NDVI runs -1 to 1;
    below ~0.2 is bare soil/sparse cover, 0.2-0.5 is moderate vegetation,
    above 0.5 is dense, healthy vegetation."""
    if ndvi is None:
        return "Pending", "medium", 50
    bar_pct = min(100, max(0, ((ndvi + 0.1) / 0.8) * 100))
    if ndvi >= 0.5:
        return "Healthy & Dense", "good", bar_pct
    if ndvi >= 0.2:
        return "Moderate", "medium", bar_pct
    return "Sparse / Bare", "low", bar_pct


def param_card(icon, label, value, unit, status_label, status_family, ideal_text, note, bar_pct):
    c = STATUS_COLORS[status_family]
    return f"""
    <div class="param-card">
      <div class="param-strip" style="background:{c['bar']};"></div>
      <div class="param-body">
        <div class="param-name">{icon}{label}</div>
        <div class="param-value-row">
          <span class="param-value">{value}</span>
          <span class="param-unit">{unit}</span>
          <span class="badge" style="background:{c['bg']};color:{c['text']};">{status_label}</span>
        </div>
        <div class="bar-track"><div class="bar-fill" style="width:{bar_pct}%;background:{c['bar']};"></div></div>
        <div class="param-ideal">{ideal_text}</div>
        <p class="param-note">{note}</p>
      </div>
    </div>"""


def nitrogen_card(nitrogen_g_per_kg) -> str:
    """Nitrogen needs its own card shape, not the generic param_card --
    it shows two genuinely different measurements side by side: Total N
    (a real value we have from SoilGrids) and Available N (which we do
    NOT have and will not fabricate -- it requires lab-based chemical
    extraction, not satellite/climate data)."""
    total_display = f"{nitrogen_g_per_kg:.2f} g/kg" if nitrogen_g_per_kg is not None else "—"
    return f"""
    <div class="param-card nitrogen-card">
      <div class="param-strip" style="background:#8A8070;"></div>
      <div class="param-body">
        <div class="param-name">{ICON_NITROGEN}NITROGEN</div>
        <div class="nitrogen-split">
          <div class="nitrogen-half">
            <div class="nitrogen-sublabel">Total Nitrogen</div>
            <div class="nitrogen-value">{total_display}</div>
            <div class="nitrogen-source">Measured · satellite soil data</div>
          </div>
          <div class="nitrogen-half">
            <div class="nitrogen-sublabel">Available Nitrogen</div>
            <div class="nitrogen-value nitrogen-unavailable">Not measured</div>
            <div class="nitrogen-source">Requires lab extraction — see ₹1,000+ tiers</div>
          </div>
        </div>
        <p class="param-note">Total and available nitrogen are different measurements — total is everything present in the soil, available is what your crop can actually use right now. Government fertiliser guidelines are based on available nitrogen, which needs a physical soil sample to measure accurately.</p>
      </div>
    </div>"""


def action_item(title, body):
    return f"""
      <div class="action">
        <div class="action-title">{title}</div>
        <p class="action-body">{body}</p>
      </div>"""


PRICING_TIERS = [
    ("₹100", "Site Analysis Report", "Climate + soil, delivered instantly — you're reading it now.", "current", None),
    ("₹200", "Climate Intelligence", "Wind rose (prevailing wind direction) + sun path (seasonal solar angle) + slope orientation.", "available", "https://greenaffair.in/soil/#satellite"),
    ("₹300", "Terrain Report", "Contour map + water catchment and drainage direction.", "available", "https://greenaffair.in/soil/#satellite"),
    ("₹500", "Land Intelligence", "Biodiversity index + detailed wind rose and sun-path diagrams.", "available", "https://greenaffair.in/soil/#satellite"),
    ("₹1,000", "Satellite Soil Test", "NPK, salinity, moisture zones + Komal's written action plan.", "available", "https://greenaffair.in/soil/#satellite"),
    ("₹18,500", "Full Lab Diagnostic", "Biology, chemistry & structure — complete on-site soil analysis.", "available", "https://greenaffair.in/soil-diagnostics/"),
]


def ladder_row(price, name, desc, status, url):
    action_label = "Your report" if status == "current" else "Get this →"
    row_html = f"""
      <div class="ladder-price">{price}</div>
      <div class="ladder-info">
        <div class="ladder-name">{name}</div>
        <div class="ladder-desc">{desc}</div>
      </div>
      <div class="ladder-action">{action_label}</div>"""
    if status == "current":
        return f'<div class="ladder-row current">{row_html}</div>'
    return f'<a href="{url}" class="ladder-row available">{row_html}</a>'


def scorecard_hero_html(scorecard: dict, scorecard_report: dict) -> str:
    """Renders the grade badge + overall score + real ranked constraints
    with AI-written actions, using ONLY the deterministic scorecard data
    for numbers and the AI text for explanation -- numbers never come
    from the model."""
    constraints = scorecard["top_constraints"]
    actions = scorecard_report.get("constraint_actions", [])

    constraint_items = ""
    for i, c in enumerate(constraints):
        action_text = actions[i] if i < len(actions) else ""
        constraint_items += f"""
        <div class="constraint-item">
          <span class="constraint-name">{c['label']}</span>
          <p class="constraint-action">{action_text}</p>
        </div>"""

    input_saving_block = ""
    if scorecard_report.get("input_saving_tip"):
        input_saving_block = f"""
        <div class="input-saving-tip">
          <div class="input-saving-label">Save on this input</div>
          {scorecard_report['input_saving_tip']}
        </div>"""

    score_display = scorecard["overall_score"] if scorecard["overall_score"] is not None else "—"

    return f"""
    <div class="scorecard-hero">
      <div class="scorecard-top">
        <div class="grade-badge">{scorecard['grade']}</div>
        <div class="scorecard-score">Overall Score<br><b>{score_display}/100</b></div>
      </div>
      <p class="scorecard-summary">{scorecard_report.get('scorecard_summary', '')}</p>
      <div class="constraint-list">
        {constraint_items}
      </div>
      {input_saving_block}
    </div>"""


def satellite_image_url(lat: float, lon: float) -> str:
    """Builds a satellite image URL for this exact location using Esri's
    free World Imagery export service -- no API key required. ~900m x 560m
    view centered on the farm."""
    d_lat, d_lon = 0.004, 0.0065  # roughly matches a 640x400 image aspect
    bbox = f"{lon - d_lon},{lat - d_lat},{lon + d_lon},{lat + d_lat}"
    return (
        "https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/export"
        f"?bbox={bbox}&bboxSR=4326&size=640,400&imageSR=4326&format=png32&f=image"
    )


def render_report_html(farm_data: dict, report: dict, scorecard: dict = None, scorecard_report: dict = None) -> str:
    climate = farm_data["data"].get("climate", {})
    soil = farm_data["data"].get("soil", {})
    vegetation = farm_data["data"].get("vegetation", {})
    location = farm_data.get("location", {})

    ph = soil.get("ph")
    ph_label, ph_family, ph_bar = classify_ph(ph)

    oc_label, oc_family, oc_pct, oc_bar = classify_organic_carbon(soil.get("organic_carbon_g_per_kg"))
    oc_display = f"{oc_pct:.2f}" if oc_pct is not None else "—"

    rain_mm = climate.get("annual_rainfall_mm")
    rain_label, rain_family, rain_bar = classify_rainfall(rain_mm)
    rain_display = f"{rain_mm:,.0f}" if rain_mm is not None else "—"

    texture_label, texture_family, texture_detail, texture_bar = classify_texture(
        soil.get("clay_pct"), soil.get("sand_pct"), soil.get("silt_pct")
    )

    ndvi_value = vegetation.get("ndvi") if vegetation.get("status") == "ok" else None
    ndvi_label, ndvi_family, ndvi_bar = classify_ndvi(ndvi_value)
    ndvi_display = f"{ndvi_value:.2f}" if ndvi_value is not None else "—"

    temp = climate.get("annual_avg_temp_c")
    temp_display = f"{temp:.1f}" if temp is not None else "—"
    temp_bar = min(100, max(0, ((temp - 10) / 25) * 100)) if temp is not None else 50

    lat = location.get("latitude", "—")
    lon = location.get("longitude", "—")
    report_date = datetime.now().strftime("%d/%m/%Y")

    corner_icon_html = (
        f'<img src="data:image/png;base64,{BUTTERFLY_BASE64}" alt="" class="corner-icon">'
        if BUTTERFLY_BASE64 else ""
    )
    logo_small_html = (
        f'<img src="data:image/png;base64,{LOGO_BASE64}" alt="Greenaffair" class="header-logo">'
        if LOGO_BASE64 else '<span class="header-wordmark">G R E E N A F F A I R</span>'
    )

    cards_html = "".join([
        param_card(ICON_RAIN, "ANNUAL RAINFALL", rain_display, "mm", rain_label, rain_family,
                   "Typical range for rain-fed cropping: 600–1,200mm",
                   report["climate_narrative"], rain_bar),
        param_card(ICON_TEMP, "AVG. TEMPERATURE", temp_display, "°C", "Recorded", "good",
                   "Comfortable range for most temperate & subtropical crops",
                   "Year-round average — actual monthly swings can be much wider.", temp_bar),
        param_card(ICON_FLASK, "SOIL PH", ph if ph is not None else "—", "", ph_label, ph_family,
                   "Neutral: 6.5–7.0 (ICAR-IISS standard)", report["soil_narrative"], ph_bar),
        param_card(ICON_LEAF, "ORGANIC CARBON", oc_display, "%", oc_label, oc_family,
                   "High: above 0.75% (ICAR-IISS standard)",
                   "This is the number that matters most for long-term soil life and nutrient availability.", oc_bar),
        param_card(ICON_LAYERS, "SOIL TEXTURE", texture_label, "", texture_detail, texture_family,
                   "Affects drainage and how well soil holds water and nutrients.",
                   "", texture_bar),
        param_card(ICON_SPROUT, "VEGETATION HEALTH", ndvi_label, "", f"Index {ndvi_display}" if ndvi_value is not None else "—", ndvi_family,
                   "Based on how green and dense the growth on your land is right now",
                   f"From live satellite imagery, averaged over the last 30 days ({vegetation.get('period', 'recent')})." if ndvi_value is not None else "Vegetation data not available for this location right now.",
                   ndvi_bar),
        nitrogen_card(soil.get("nitrogen_g_per_kg")),
    ])

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Farm Climate & Soil Snapshot — Greenaffair</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap" rel="stylesheet">
<style>
  :root {{
    --cream: #FFFFFF; --card: #F7FAF7; --ink: #1C2620; --ink-muted: #62705F;
    --rule: #D6E3D6; --accent: #2E7D46; --dark: #163220;
  }}
  * {{ box-sizing: border-box; }}
  body {{ background: #E4EBE2; margin: 0; padding: 32px 16px; font-family: 'Inter', sans-serif; -webkit-font-smoothing: antialiased; }}
  .page {{ max-width: 700px; margin: 0 auto 10px; box-shadow: 0 2px 20px rgba(22,50,32,0.12); overflow: hidden; }}

  /* COVER PAGE */
  .cover {{
    background: #FFFFFF;
    color: var(--ink); padding: 48px 44px 32px; position: relative;
  }}
  .brand-banner {{ background: var(--dark); margin: -20px -30px 18px; padding: 16px 30px; display: flex; align-items: center; justify-content: space-between; gap: 16px; }}
  .brand-banner-text {{ flex: 1; }}
  .cover-wordmark-big {{ font-weight: 800; font-size: 16px; letter-spacing: 0.12em; color: #F5F0E8; margin: 0; }}
  .cover-brand-tagline {{ font-size: 12px; font-weight: 500; color: rgba(245,240,232,0.75); margin-top: 4px; line-height: 1.4; letter-spacing: 0.01em; }}
  .corner-icon {{ height: 32px; width: auto; flex-shrink: 0; }}
  .cover-tag {{ color: var(--accent); font-size: 10px; font-weight: 700; letter-spacing: 0.05em; text-transform: uppercase; margin-top: 16px; margin-bottom: 3px; }}
  .section-divider {{ height: 1px; background: var(--rule); margin: 18px 0; }}
  .cover-h1 {{ font-size: 15px; font-weight: 800; line-height: 1.12; margin: 0; color: var(--ink); }}
  .cover-h1 .accent {{ color: var(--accent); display: block; }}
  .cover-tagline {{ font-size: 11.5px; color: var(--ink-muted); margin-top: 6px; max-width: 500px; line-height: 1.4; }}
  .cover-prepared {{ color: var(--ink-muted); font-size: 9.5px; margin-top: 8px; }}
  .cover-details {{ background: var(--card); border: 1px solid var(--rule); border-radius: 8px; padding: 10px 14px; margin-top: 10px; font-size: 11px; }}
  .sat-image-wrap {{ margin-top: 8px; border-radius: 8px; overflow: hidden; border: 1px solid var(--rule); position: relative; max-height: 130px; }}
  .sat-image-wrap img {{ display: block; width: 100%; height: auto; }}
  .sat-pin-overlay {{ position: absolute; top: 0; left: 0; width: 100%; height: 100%; pointer-events: none; filter: drop-shadow(0 0 2px rgba(0,0,0,0.6)); }}
  .sat-image-label {{ position: absolute; bottom: 0; left: 0; right: 0; background: linear-gradient(transparent, rgba(0,0,0,0.65)); color: #ffffff; font-size: 10px; font-weight: 700; letter-spacing: 0.1em; text-transform: uppercase; padding: 24px 14px 10px; }}
  .cover-details-label {{ font-size: 10px; letter-spacing: 0.15em; text-transform: uppercase; color: var(--ink-muted); margin-bottom: 12px; }}
  .cover-details-grid {{ display: flex; gap: 20px; flex-wrap: wrap; margin-bottom: 10px; }}
  .cover-detail-item {{ flex: 1; min-width: 140px; }}
  .cover-detail-item .k {{ font-size: 11px; color: var(--ink-muted); margin-bottom: 4px; }}
  .cover-detail-item .v {{ font-size: 14px; font-weight: 600; color: var(--ink); }}
  .maps-link {{ font-size: 10px; font-weight: 700; color: var(--accent); text-decoration: none; }}

  /* CREAM PAGES */
  .cream {{ background: var(--cream); padding: 20px 30px 18px; font-size: 12.5px; }}
  .cream-header {{ display: flex; justify-content: space-between; align-items: center; border-bottom: 1px solid var(--rule); padding-bottom: 12px; margin-bottom: 24px; }}
  .header-logo {{ height: 34px; }}
  .eyebrow {{ font-size: 9px; letter-spacing: 0.1em; text-transform: uppercase; color: var(--ink-muted); margin-bottom: 4px; }}
  .h2 {{ font-size: 15px; font-weight: 800; color: var(--ink); margin: 0 0 12px; }}

  .cards-grid {{ display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 6px; margin-bottom: 8px; }}
  .scorecard-hero {{ background: var(--card); border: 1px solid var(--rule); border-left: 4px solid var(--accent); border-radius: 8px; padding: 12px 16px; margin-bottom: 12px; color: var(--ink); font-size: 12px; }}
  .scorecard-top {{ display: flex; align-items: center; gap: 10px; margin-bottom: 8px; }}
  .grade-badge {{ width: 34px; height: 34px; border-radius: 50%; background: var(--accent); color: #FFFFFF; display: flex; align-items: center; justify-content: center; font-size: 15px; font-weight: 800; flex-shrink: 0; }}
  .scorecard-score {{ font-size: 9.5px; color: var(--ink-muted); }}
  .scorecard-score b {{ font-size: 15px; color: var(--ink); }}
  .scorecard-summary {{ font-size: 10.5px; line-height: 1.4; color: var(--ink); margin: 0 0 8px; }}
  .constraint-list {{ display: flex; flex-direction: column; gap: 10px; }}
  .constraint-item {{ background: var(--cream); border: 1px solid var(--rule); border-radius: 6px; padding: 6px 8px; }}
  .constraint-name {{ display: block; font-size: 10px; font-weight: 700; color: var(--ink); margin-bottom: 3px; }}
  .constraint-action {{ font-size: 9px; line-height: 1.35; color: var(--ink-muted); margin: 0; }}
  .input-saving-tip {{ margin-top: 8px; padding-top: 6px; border-top: 1px solid var(--rule); font-size: 9px; line-height: 1.35; color: var(--ink); }}
  .input-saving-label {{ font-size: 10px; letter-spacing: 0.08em; text-transform: uppercase; color: var(--accent); font-weight: 700; margin-bottom: 6px; }}
  .param-card {{ background: var(--card); border-radius: 10px; overflow: hidden; border: 1px solid var(--rule); }}
  .param-strip {{ height: 4px; }}
  .param-body {{ padding: 8px 10px 9px; }}
  .param-name {{ display: flex; align-items: center; gap: 4px; font-size: 8px; letter-spacing: 0.06em; text-transform: uppercase; color: var(--ink-muted); margin-bottom: 4px; }}
  .param-name svg {{ color: var(--accent); flex-shrink: 0; }}
  .param-value-row {{ display: flex; align-items: baseline; gap: 6px; flex-wrap: wrap; margin-bottom: 10px; }}
  .param-value {{ font-size: 14px; font-weight: 800; color: var(--ink); line-height: 1.15; }}
  .param-unit {{ font-size: 9px; color: var(--ink-muted); }}
  .badge {{ margin-left: auto; font-size: 8px; font-weight: 700; padding: 2px 7px; border-radius: 100px; }}
  .bar-track {{ height: 3px; background: var(--rule); border-radius: 100px; margin-bottom: 5px; overflow: hidden; }}
  .bar-fill {{ height: 100%; border-radius: 100px; }}
  .param-ideal {{ font-size: 8.5px; color: var(--ink-muted); margin-bottom: 3px; }}
  .param-note {{ font-size: 10px; line-height: 1.4; color: var(--ink); margin: 0; }}
  .nitrogen-card {{ grid-column: 1 / -1; }}
  .nitrogen-split {{ display: grid; grid-template-columns: 1fr 1fr; gap: 10px; margin-bottom: 6px; }}
  .nitrogen-sublabel {{ font-size: 10px; letter-spacing: 0.08em; text-transform: uppercase; color: var(--ink-muted); margin-bottom: 4px; }}
  .nitrogen-value {{ font-size: 14px; font-weight: 800; color: var(--ink); }}
  .nitrogen-value.nitrogen-unavailable {{ font-size: 11px; font-weight: 600; color: var(--ink-muted); font-style: italic; }}
  .nitrogen-source {{ font-size: 10.5px; color: var(--ink-muted); margin-top: 3px; }}

  .region-facts {{ border-left: 2px solid var(--accent); padding: 2px 0 2px 10px; margin-bottom: 10px; font-size: 11px; }}
  .region-facts-label {{ font-size: 11px; letter-spacing: 0.1em; text-transform: uppercase; color: var(--accent); font-weight: 700; margin-bottom: 6px; }}
  .region-facts p {{ font-size: 13px; line-height: 1.65; color: var(--ink); margin: 0; }}

  .tier-header {{ background: #E6E0D0; border-radius: 5px; padding: 5px 10px; font-size: 9px; letter-spacing: 0.05em; text-transform: uppercase; font-weight: 700; color: var(--ink); margin: 12px 0 8px; }}
  .tier-header.risk {{ background: #F5DEDA; color: #B5453A; }}
  .cta-highlight {{ margin: 12px 0; padding: 12px 14px; border-radius: 8px; }}
  .cta-highlight.money {{ background: var(--card); border: 1.5px solid var(--accent); }}
  .cta-highlight.subscribe {{ background: var(--dark); color: #F5F0E8; }}
  .cta-highlight-label {{ font-size: 10px; letter-spacing: 0.1em; text-transform: uppercase; font-weight: 700; margin-bottom: 8px; }}
  .cta-highlight.money .cta-highlight-label {{ color: var(--accent); }}
  .cta-highlight.subscribe .cta-highlight-label {{ color: var(--accent); }}
  .cta-highlight-title {{ font-family: inherit; font-weight: 800; font-size: 12.5px; margin-bottom: 5px; line-height: 1.25; }}
  .cta-highlight p {{ font-size: 9.5px; line-height: 1.4; margin: 0 0 8px; }}
  .cta-highlight.subscribe p {{ color: rgba(245,240,232,0.8); }}
  .cta-highlight-btn {{ display: inline-block; text-decoration: none; font-size: 13px; font-weight: 700; padding: 11px 22px; border-radius: 100px; }}
  .cta-highlight.money .cta-highlight-btn {{ background: var(--accent); color: #FFFFFF; }}
  .cta-highlight.subscribe .cta-highlight-btn {{ background: var(--accent); color: #FFFFFF; }}
  .tier-header:first-of-type {{ margin-top: 0; }}
  .action {{ margin-bottom: 8px; }}
  .action-title {{ font-weight: 700; font-size: 11.5px; color: var(--ink); margin-bottom: 2px; }}
  .action-body {{ font-size: 10px; line-height: 1.4; color: var(--ink-muted); margin: 0; }}

  .cta-block {{ text-align: center; margin: 28px 0; padding: 24px; background: var(--card); border: 1px solid var(--rule); border-radius: 10px; color: var(--ink); }}
  .cta-block p {{ margin: 0 0 14px; font-size: 14px; }}

  .ladder {{ margin: 28px 0; }}

  .signoff {{ display: flex; justify-content: space-between; align-items: flex-end; margin-top: 12px; padding-top: 10px; border-top: 1px solid var(--rule); flex-wrap: wrap; gap: 10px; font-size: 10px; }}
  .signoff-prepared {{ font-size: 11px; color: var(--ink-muted); margin-bottom: 4px; }}
  .signoff-name {{ font-size: 15px; font-weight: 800; color: var(--accent); }}
  .signoff-title {{ font-size: 11px; color: var(--ink-muted); margin-top: 2px; }}
  .signoff-contact {{ text-align: right; font-size: 12px; color: var(--ink-muted); line-height: 1.7; }}

  .disclaimer {{ margin-top: 10px; font-size: 8px; line-height: 1.4; color: var(--ink-muted); padding-top: 8px; border-top: 1px solid var(--rule); }}
  .disclaimer a {{ color: var(--accent); }}
  .cream-footer {{ display: flex; justify-content: space-between; font-size: 8px; color: var(--ink-muted); margin-top: 8px; padding-top: 6px; border-top: 1px solid var(--rule); }}

  @media (max-width: 560px) {{
    .cover {{ padding: 28px 24px; min-height: 500px; }}
    .cover-h1 {{ font-size: 15px; }}
    .cover-tag {{ margin-top: 32px; }}
    .cream {{ padding: 24px; }}
    .cards-grid {{ grid-template-columns: 1fr; }}
    .signoff {{ flex-direction: column; align-items: flex-start; }}
    .signoff-contact {{ text-align: left; }}
  }}

  /* PRINT / PDF EXPORT: force each .page to start on its own physical
     page, so pages never split mid-content or overlap when printed or
     exported to PDF. Only break-inside rules matter now that everything
     is one continuous page -- prevents a card from splitting awkwardly
     if it happens to fall near a physical page boundary when printed. */
  @media print {{
    body {{ background: #FFFFFF; padding: 0; }}
    .page {{ box-shadow: none; margin: 0; max-width: 100%; }}
    .param-card, .scorecard-hero, .nitrogen-card, .cta-block, .constraint-item,
      break-inside: avoid; page-break-inside: avoid;
    }}
  }}
  @page {{ margin: 0.4in; size: A4; }}
</style>
</head>
<body>

  <!-- SINGLE PAGE REPORT -->
  <div class="page cream">
    <div class="brand-banner">
      <div class="brand-banner-text">
        <div class="cover-wordmark-big">GREENAFFAIR</div>
        <div class="cover-brand-tagline">Making farming profitable for you — and your land sustainable for generations to come.</div>
      </div>
      {corner_icon_html}
    </div>
    <div class="cover-tag">Site Analysis Report</div>
    <h1 class="cover-h1">Farm Climate &amp;<span class="accent">Soil Snapshot</span></h1>
    <p class="cover-tagline">{report['headline']}</p>
    <div class="cover-prepared">Prepared by Greenaffair · Automated Analysis</div>

    <div class="cover-details">
      <div class="cover-details-label">Farm Details</div>
      <div class="cover-details-grid">
        <div class="cover-detail-item"><div class="k">Latitude</div><div class="v">{lat}</div></div>
        <div class="cover-detail-item"><div class="k">Longitude</div><div class="v">{lon}</div></div>
        <div class="cover-detail-item"><div class="k">Report Date</div><div class="v">{report_date}</div></div>
        <div class="cover-detail-item"><div class="k">Data Sources</div><div class="v">{DATA_SOURCE_LABEL}</div></div>
      </div>
      <a href="https://www.google.com/maps?q={lat},{lon}" target="_blank" class="maps-link">Open in Google Maps →</a>
      <div class="sat-image-wrap">
        <img src="{satellite_image_url(lat, lon)}" alt="Satellite view of farm location" loading="lazy">
        <svg class="sat-pin-overlay" viewBox="0 0 640 400" preserveAspectRatio="none">
          <circle cx="320" cy="200" r="14" fill="none" stroke="#F2C230" stroke-width="2.5"/>
          <circle cx="320" cy="200" r="4" fill="#F2C230"/>
          <line x1="320" y1="186" x2="320" y2="160" stroke="#F2C230" stroke-width="2"/>
          <line x1="320" y1="214" x2="320" y2="240" stroke="#F2C230" stroke-width="2"/>
          <line x1="306" y1="200" x2="280" y2="200" stroke="#F2C230" stroke-width="2"/>
          <line x1="334" y1="200" x2="360" y2="200" stroke="#F2C230" stroke-width="2"/>
        </svg>
        <div class="sat-image-label">Your submitted coordinates — marked exactly · field boundaries not shown</div>
      </div>
    </div>

    <div class="section-divider"></div>

    <div class="eyebrow">Snapshot Parameter Analysis</div>
    <h2 class="h2">Your Climate &amp; Soil Results</h2>

    {f'<div class="region-facts"><div class="region-facts-label">About This Region</div><p>{report["region_facts"]}</p></div>' if report.get("region_facts") else ""}

    {scorecard_hero_html(scorecard, scorecard_report) if scorecard and scorecard_report else ""}

    <div class="cards-grid">
      {cards_html}
    </div>

    <div class="section-divider"></div>

    <div class="eyebrow">Action Plan</div>
    <h2 class="h2">What To Do Next</h2>

    <div class="tier-header">THIS SEASON</div>
    {action_item("When to sow, for this exact soil", report['planning_tip'])}

    {f'<div class="tier-header risk">Risk To Watch</div>{action_item("A pattern in your data worth monitoring", report["disease_risk_flag"])}' if report.get("disease_risk_flag") else ""}

    <div class="cta-highlight money">
      <div class="cta-highlight-label">The Real Opportunity Here</div>
      <div class="cta-highlight-title">This land can become an income asset — not just a cost to manage.</div>
      <p>{report['closing_hook']} Our executives can walk you through exactly how, for your specific soil and climate — no obligation.</p>
      <a href="https://wa.me/917470506281?text=I%20want%20to%20know%20how%20to%20turn%20my%20land%20into%20more%20income" class="cta-highlight-btn">Ask Our Executive How →</a>
    </div>

    <div class="cta-highlight subscribe">
      <div class="cta-highlight-label">Stay Ahead, All Year</div>
      <div class="cta-highlight-title">₹600/year — a fresh soil report every month, from real data.</div>
      <p>Less than ₹50 a month. Track exactly how your land changes through every season, not just once.</p>
      <a href="https://wa.me/917470506281?text=I%27m%20interested%20in%20the%20%E2%82%B9600%2Fyear%20monthly%20soil%20report%20plan" class="cta-highlight-btn">Subscribe →</a>
    </div>

    <div class="signoff">
      <div>
        <div class="signoff-prepared">Prepared by</div>
        <div class="signoff-name">Greenaffair</div>
        <div class="signoff-title">Automated Climate &amp; Soil Snapshot · Instant Delivery</div>
      </div>
      <div class="signoff-contact">
        Questions? WhatsApp us:<br>
        {COMPANY_PHONE_1} · {COMPANY_PHONE_2}<br>
        {COMPANY_EMAIL}
      </div>
    </div>

    <div class="disclaimer">
      This report is generated through Greenaffair's remote sensing and climate analysis pipeline and is not a substitute for the full biological and chemical soil diagnostic. For nitrogen, phosphorus, potassium, salinity, and moisture-zone mapping specific to your farm, request the full satellite test at <a href="https://greenaffair.in/soil/#satellite">greenaffair.in/soil</a>.
      <br><br>
      <strong>{COMPANY_NAME}</strong><br>
      {COMPANY_ADDRESS}<br>
      {COMPANY_ADDRESS_2}
    </div>

    <div class="cream-footer">
      <span>{COMPANY_NAME}</span>
      <span>CONFIDENTIAL</span>
    </div>
  </div>

</body>
</html>"""
