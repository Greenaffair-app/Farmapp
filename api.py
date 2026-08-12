"""
Farm Data API
-------------
A small web API that wraps orchestrator.py so a website / app can call
one URL and get back farm data -- with caching, so two farmers near
each other don't trigger duplicate calls to NASA/SoilGrids.

Requires: pip install fastapi uvicorn requests --break-system-packages

Run it:
    python api.py
Then open in a browser:
    http://localhost:8000/docs        <- interactive API tester
    http://localhost:8000/farm-report?lat=30.3398&lon=76.3869

This uses SQLite (a single file, no server to install) for caching.
When you're ready to go to production with real user accounts and
payments, swap this for Postgres -- the table shape stays the same.
"""

import json
import sqlite3
import time
from contextlib import contextmanager

from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse

from orchestrator import fetch_farm_data
from report_generator import generate_basic_report, generate_complete_report
from report_template import render_report_html
from scorecard import build_scorecard
from apply_page import APPLY_PAGE_HTML

DB_PATH = "farm_cache.db"
CACHE_MAX_AGE_SECONDS = 30 * 24 * 60 * 60  # 30 days -- climate/soil data barely changes
REPORT_CACHE_MAX_AGE_SECONDS = 30 * 24 * 60 * 60  # reports don't need to be regenerated often either

app = FastAPI(title="Farm Data API")

# Lets a website on a different domain call this API from the browser.
# Lock this down to your actual site domain before going live.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET"],
)


@contextmanager
def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS farm_cache (
            grid_key TEXT PRIMARY KEY,
            latitude REAL,
            longitude REAL,
            data TEXT,
            fetched_at REAL
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS report_cache (
            report_key TEXT PRIMARY KEY,
            grid_key TEXT,
            language TEXT,
            report_text TEXT,
            generated_at REAL
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS structured_report_cache (
            report_key TEXT PRIMARY KEY,
            grid_key TEXT,
            language TEXT,
            report_json TEXT,
            generated_at REAL
        )
    """)
    try:
        yield conn
    finally:
        conn.close()


def grid_key_for(lat: float, lon: float) -> str:
    """Rounds coordinates to a ~11km grid cell so nearby farms share
    a cache entry instead of each triggering fresh API calls."""
    return f"{round(lat, 1)},{round(lon, 1)}"


def get_or_fetch_farm_data(conn, lat: float, lon: float) -> dict:
    """Shared by both endpoints -- checks cache first, falls back to a
    live API call, and writes fresh data back to the cache.

    Important: a cached result is only trusted if soil data actually
    succeeded. If a previous fetch hit a transient error (e.g. SoilGrids
    returning 503 Service Unavailable), we do NOT treat that as a valid
    30-day cache entry -- we retry fresh instead, so a temporary outage
    on their end doesn't get "stuck" showing Pending for a month.
    """
    key = grid_key_for(lat, lon)

    row = conn.execute(
        "SELECT data, fetched_at FROM farm_cache WHERE grid_key = ?", (key,)
    ).fetchone()

    if row and (time.time() - row[1]) < CACHE_MAX_AGE_SECONDS:
        cached_result = json.loads(row[0])
        soil_status = cached_result.get("data", {}).get("soil", {}).get("status")
        if soil_status == "ok":
            cached_result["cache_hit"] = True
            return cached_result
        # Soil data failed last time -- don't trust this cache entry, retry fresh below

    result = fetch_farm_data(lat, lon)
    result["cache_hit"] = False

    # Only write to cache if soil data actually succeeded -- an error
    # result is never worth caching for 30 days, since the whole point
    # of caching is reusing something reliable, not a known failure.
    soil_status = result.get("data", {}).get("soil", {}).get("status")
    if soil_status == "ok":
        conn.execute(
            """INSERT INTO farm_cache (grid_key, latitude, longitude, data, fetched_at)
               VALUES (?, ?, ?, ?, ?)
               ON CONFLICT(grid_key) DO UPDATE SET
                   data = excluded.data, fetched_at = excluded.fetched_at""",
            (key, lat, lon, json.dumps(result), time.time()),
        )
        conn.commit()

    return result


@app.get("/farm-report")
def farm_report(
    lat: float = Query(..., ge=-90, le=90, description="Latitude"),
    lon: float = Query(..., ge=-180, le=180, description="Longitude"),
):
    """Raw data endpoint -- returns the JSON numbers. Useful for debugging
    or for your own dashboard, but not what you'd show a farmer directly."""
    with get_db() as conn:
        return get_or_fetch_farm_data(conn, lat, lon)


@app.get("/farm-report-readable")
def farm_report_readable(
    lat: float = Query(..., ge=-90, le=90, description="Latitude"),
    lon: float = Query(..., ge=-180, le=180, description="Longitude"),
    language: str = Query("English", description="Report language, e.g. English, Hindi, Punjabi"),
):
    """The real product endpoint: location in, plain-language AI report out.
    This is what your website/WhatsApp flow should call."""
    grid_key = grid_key_for(lat, lon)
    report_key = f"{grid_key}:{language.lower()}"

    with get_db() as conn:
        row = conn.execute(
            "SELECT report_text, generated_at FROM report_cache WHERE report_key = ?",
            (report_key,),
        ).fetchone()

        if row and (time.time() - row[1]) < REPORT_CACHE_MAX_AGE_SECONDS:
            return {
                "location": {"latitude": lat, "longitude": lon},
                "language": language,
                "report": row[0],
                "cache_hit": True,
            }

        # Step 1: get the underlying numbers (cached or fresh)
        farm_data = get_or_fetch_farm_data(conn, lat, lon)

        # Step 2: turn them into a plain-language report via Claude
        report_text = generate_basic_report(farm_data, language=language)

        conn.execute(
            """INSERT INTO report_cache (report_key, grid_key, language, report_text, generated_at)
               VALUES (?, ?, ?, ?, ?)
               ON CONFLICT(report_key) DO UPDATE SET
                   report_text = excluded.report_text, generated_at = excluded.generated_at""",
            (report_key, grid_key, language, report_text, time.time()),
        )
        conn.commit()

        return {
            "location": {"latitude": lat, "longitude": lon},
            "language": language,
            "report": report_text,
            "cache_hit": False,
        }


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/apply", response_class=HTMLResponse)
def apply_form():
    """Serves the free assessment intake form directly -- a real,
    shareable link with an actual form (WhatsApp number, coordinates,
    optional name/address) rather than a fixed report link. Useful for
    quick testing without needing WordPress set up yet. The form's JS
    calls this same server's own endpoints (same-origin, no URL to
    update if the domain ever changes again)."""
    return APPLY_PAGE_HTML


def get_or_generate_report_html(lat: float, lon: float, language: str) -> str:
    """Shared by both /farm-report-styled and /farm-report-pdf -- returns
    the fully rendered HTML string, using cache where possible.

    Same class of fix as get_or_fetch_farm_data above: a cached AI-written
    report is only trusted if soil data was actually available (status
    "ok") when it was generated. If it was written during a soil-data
    outage, the AI's narrative may reference missing soil data even
    though the underlying numbers have since recovered -- so we track
    that and regenerate the narrative once real data is available again,
    rather than serving stale text for up to 30 days.
    """
    grid_key = grid_key_for(lat, lon)
    report_key = f"{grid_key}:{language.lower()}"

    with get_db() as conn:
        row = conn.execute(
            "SELECT report_json, generated_at FROM structured_report_cache WHERE report_key = ?",
            (report_key,),
        ).fetchone()

        farm_data = get_or_fetch_farm_data(conn, lat, lon)
        scorecard = build_scorecard(farm_data)
        soil_ok_now = farm_data.get("data", {}).get("soil", {}).get("status") == "ok"

        if row and (time.time() - row[1]) < REPORT_CACHE_MAX_AGE_SECONDS:
            cached = json.loads(row[0])
            soil_ok_when_cached = cached.get("_soil_status_at_generation") == "ok"
            # Trust the cache UNLESS soil just became available and the
            # cached narrative was written without it -- that's the one
            # case where regenerating is actually worth the AI cost.
            if soil_ok_when_cached or not soil_ok_now:
                return render_report_html(farm_data, cached, scorecard, cached)
            # else: fall through and regenerate fresh below

        report = generate_complete_report(farm_data, scorecard, language=language)
        report["_soil_status_at_generation"] = "ok" if soil_ok_now else "unavailable"

        conn.execute(
            """INSERT INTO structured_report_cache (report_key, grid_key, language, report_json, generated_at)
               VALUES (?, ?, ?, ?, ?)
               ON CONFLICT(report_key) DO UPDATE SET
                   report_json = excluded.report_json, generated_at = excluded.generated_at""",
            (report_key, grid_key, language, json.dumps(report), time.time()),
        )
        conn.commit()

        return render_report_html(farm_data, report, scorecard, report)


@app.get("/farm-report-styled", response_class=HTMLResponse)
def farm_report_styled(
    lat: float = Query(..., ge=-90, le=90, description="Latitude"),
    lon: float = Query(..., ge=-180, le=180, description="Longitude"),
    language: str = Query("English", description="Report language, e.g. English, Hindi, Punjabi"),
):
    """Returns the fully styled, Greenaffair-branded HTML report -- this is
    what you'd link to directly or embed in an iframe on your website."""
    return get_or_generate_report_html(lat, lon, language)


@app.get("/farm-report-pdf")
def farm_report_pdf(
    lat: float = Query(..., ge=-90, le=90, description="Latitude"),
    lon: float = Query(..., ge=-180, le=180, description="Longitude"),
    language: str = Query("English", description="Report language, e.g. English, Hindi, Punjabi"),
):
    """Returns the report as a real downloadable PDF file -- this is what
    the 'Download Report' button on your website should link to. Renders
    the same HTML as /farm-report-styled, then converts it to PDF
    server-side using a headless browser (Playwright), so the farmer gets
    one click and an actual file, not a print dialog."""
    from playwright.sync_api import sync_playwright
    from fastapi.responses import Response

    html = get_or_generate_report_html(lat, lon, language)

    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        page.set_content(html, wait_until="networkidle")
        pdf_bytes = page.pdf(print_background=True, format="A4")
        browser.close()

    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename=Greenaffair_Farm_Report_{lat}_{lon}.pdf"},
    )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("api:app", host="0.0.0.0", port=8000, reload=True)
