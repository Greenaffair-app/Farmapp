"""
Farm Data Orchestrator
-----------------------
Given a latitude/longitude, this pulls data from multiple free,
no-API-key data sources in PARALLEL, normalizes each into a common
shape, and returns one merged JSON object ready to hand to an
AI report generator or store in a database.

Data sources wired up:
  1. NASA POWER      -> climate: temperature, rainfall, humidity, wind, solar radiation (free, no key)
  2. ISRIC SoilGrids  -> soil: pH, organic carbon, texture, nitrogen, CEC,
                          bulk density, water retention (free, no key)
  3. Open-Elevation   -> elevation (free, no key)
  4. Copernicus Sentinel-2 -> NDVI / vegetation health (free, but requires
                          OAuth credentials -- see get_vegetation_data() below)

Requires: pip install requests --break-system-packages

Usage:
    python orchestrator.py 30.3398 76.3869   # Patiala, Punjab example
"""

import sys
import os
import json
import time
from datetime import datetime, timedelta
from concurrent.futures import ThreadPoolExecutor, as_completed

import requests

TIMEOUT = 15  # seconds per API call


def get_climate_data(lat: float, lon: float) -> dict:
    """NASA POWER climatology endpoint: long-term monthly averages.
    No API key needed. Returns month-by-month climate normals.
    """
    url = "https://power.larc.nasa.gov/api/temporal/climatology/point"
    params = {
        "parameters": "T2M,T2M_MAX,T2M_MIN,PRECTOTCORR,RH2M,ALLSKY_SFC_SW_DWN,WS2M,WD2M",
        "community": "AG",  # Agroclimatology community
        "longitude": lon,
        "latitude": lat,
        "format": "JSON",
    }
    try:
        resp = requests.get(url, params=params, timeout=TIMEOUT)
        resp.raise_for_status()
        raw = resp.json()["properties"]["parameter"]

        months = ["JAN", "FEB", "MAR", "APR", "MAY", "JUN",
                  "JUL", "AUG", "SEP", "OCT", "NOV", "DEC"]

        # NASA POWER reports PRECTOTCORR as a daily-average rate (mm/day),
        # even for monthly/annual climatology values -- NOT a total. We
        # convert to real totals here using each month's day count, since
        # a farmer needs "how much rain falls" not "average daily rate".
        days_in_month = {
            "JAN": 31, "FEB": 28.25, "MAR": 31, "APR": 30, "MAY": 31, "JUN": 30,
            "JUL": 31, "AUG": 31, "SEP": 30, "OCT": 31, "NOV": 30, "DEC": 31,
        }
        monthly_rainfall_total_mm = {
            m: round(raw["PRECTOTCORR"].get(m) * days_in_month[m], 1)
            if raw["PRECTOTCORR"].get(m) is not None else None
            for m in months
        }
        annual_rainfall_total_mm = round(sum(
            v for v in monthly_rainfall_total_mm.values() if v is not None
        ), 1) if any(v is not None for v in monthly_rainfall_total_mm.values()) else None

        return {
            "source": "NASA POWER",
            "status": "ok",
            "monthly_avg_temp_c": {m: raw["T2M"].get(m) for m in months},
            "monthly_max_temp_c": {m: raw["T2M_MAX"].get(m) for m in months},
            "monthly_min_temp_c": {m: raw["T2M_MIN"].get(m) for m in months},
            "monthly_rainfall_mm": monthly_rainfall_total_mm,  # real monthly totals now, not daily rate
            "monthly_humidity_pct": {m: raw["RH2M"].get(m) for m in months},
            "monthly_solar_radiation": {m: raw["ALLSKY_SFC_SW_DWN"].get(m) for m in months},
            "monthly_wind_speed_ms": {m: raw["WS2M"].get(m) for m in months},
            "monthly_wind_direction_deg": {m: raw["WD2M"].get(m) for m in months},
            "annual_avg_temp_c": raw["T2M"].get("ANN"),
            "annual_rainfall_mm": annual_rainfall_total_mm,  # real annual total now, not daily rate
            "annual_avg_humidity_pct": raw["RH2M"].get("ANN"),
            "annual_avg_wind_speed_ms": raw["WS2M"].get("ANN"),
            "annual_avg_wind_direction_deg": raw["WD2M"].get("ANN"),
            "annual_avg_solar_radiation": raw["ALLSKY_SFC_SW_DWN"].get("ANN"),
        }
    except Exception as e:
        return {"source": "NASA POWER", "status": "error", "error": str(e)}


def _query_soilgrids_point(lat: float, lon: float) -> dict:
    """Single raw SoilGrids query at one exact point. Returns a dict of
    extracted values (may contain Nones if that exact pixel has no data)."""
    url = "https://rest.isric.org/soilgrids/v2.0/properties/query"
    params = {
        "lon": lon,
        "lat": lat,
        "property": ["phh2o", "soc", "clay", "sand", "silt", "nitrogen", "cec", "bdod", "wv0033"],
        "depth": "0-5cm",
        "value": "mean",
    }
    resp = requests.get(url, params=params, timeout=TIMEOUT)
    resp.raise_for_status()
    layers = resp.json()["properties"]["layers"]

    def extract(name):
        """Pulls the value AND uses the API's own conversion factor
        (unit_measure.d_factor) rather than a hardcoded one -- safer,
        since different properties use different factors and this
        adapts automatically if SoilGrids changes theirs."""
        for layer in layers:
            if layer["name"] == name:
                val = layer["depths"][0]["values"]["mean"]
                if val is None:
                    return None
                d_factor = layer.get("unit_measure", {}).get("d_factor", 1)
                return round(val / d_factor, 2)
        return None

    return {
        "ph": extract("phh2o"),
        "organic_carbon_g_per_kg": extract("soc"),
        "clay_pct": extract("clay"),
        "sand_pct": extract("sand"),
        "silt_pct": extract("silt"),
        "nitrogen_g_per_kg": extract("nitrogen"),
        "cec_cmol_per_kg": extract("cec"),
        "bulk_density_kg_dm3": extract("bdod"),
        "water_retention_pct": extract("wv0033"),
    }


def get_soil_data(lat: float, lon: float) -> dict:
    """ISRIC SoilGrids: global soil property predictions at 250m resolution.
    No API key needed. Pulls the core texture/pH/carbon set plus nitrogen,
    CEC (nutrient-holding capacity), bulk density (compaction), and water
    retention -- the extra fields needed for a full 12-15 parameter report.

    If the exact point has no data (common on a building/water/road pixel),
    automatically tries four nearby points (~250m offsets, matching
    SoilGrids' own resolution) and uses the first one with real data --
    so "Pending" only shows up when NO nearby soil data exists at all,
    not just because the exact pin landed on a bad pixel.
    """
    offsets = [(0, 0), (0.0025, 0), (-0.0025, 0), (0, 0.0025), (0, -0.0025)]
    try:
        for d_lat, d_lon in offsets:
            values = _query_soilgrids_point(lat + d_lat, lon + d_lon)
            if any(v is not None for v in values.values()):
                return {"source": "ISRIC SoilGrids", "status": "ok", **values}
        # All attempts came back empty -- genuinely no coverage here
        return {
            "source": "ISRIC SoilGrids", "status": "ok",
            "ph": None, "organic_carbon_g_per_kg": None, "clay_pct": None,
            "sand_pct": None, "silt_pct": None, "nitrogen_g_per_kg": None,
            "cec_cmol_per_kg": None, "bulk_density_kg_dm3": None, "water_retention_pct": None,
        }
    except Exception as e:
        return {"source": "ISRIC SoilGrids", "status": "error", "error": str(e)}


def get_elevation(lat: float, lon: float) -> dict:
    """Open-Elevation: free elevation lookup. Can be flaky/rate-limited --
    swap for opentopodata.org (self-hostable) if this becomes unreliable
    at scale.
    """
    url = "https://api.open-elevation.com/api/v1/lookup"
    params = {"locations": f"{lat},{lon}"}
    try:
        resp = requests.get(url, params=params, timeout=TIMEOUT)
        resp.raise_for_status()
        result = resp.json()["results"][0]
        return {
            "source": "Open-Elevation",
            "status": "ok",
            "elevation_m": result.get("elevation"),
        }
    except Exception as e:
        return {"source": "Open-Elevation", "status": "error", "error": str(e)}


def _get_copernicus_token():
    """OAuth2 client-credentials exchange -- trades the stored Client ID
    and Secret for a short-lived access token. Tokens expire in about an
    hour, so we fetch a fresh one on every request rather than caching it;
    this call is fast and it keeps the logic simple.
    """
    client_id = os.environ.get("COPERNICUS_CLIENT_ID")
    client_secret = os.environ.get("COPERNICUS_CLIENT_SECRET")
    if not client_id or not client_secret:
        return None

    token_url = "https://identity.dataspace.copernicus.eu/auth/realms/CDSE/protocol/openid-connect/token"
    resp = requests.post(
        token_url,
        data={
            "grant_type": "client_credentials",
            "client_id": client_id,
            "client_secret": client_secret,
        },
        timeout=TIMEOUT,
    )
    resp.raise_for_status()
    return resp.json()["access_token"]


def get_vegetation_data(lat: float, lon: float) -> dict:
    """Sentinel-2 NDVI (vegetation health) via the Copernicus Data Space
    Ecosystem's Sentinel Hub Statistical API. Averages over the last 30
    days to smooth out any single cloudy pass.

    Requires two environment variables (free OAuth credentials from
    dataspace.copernicus.eu -> Sentinel Hub dashboard -> User Settings ->
    OAuth clients):
        COPERNICUS_CLIENT_ID
        COPERNICUS_CLIENT_SECRET
    """
    try:
        token = _get_copernicus_token()
        if not token:
            return {
                "source": "Copernicus Sentinel-2",
                "status": "not_configured",
                "note": "Requires COPERNICUS_CLIENT_ID and COPERNICUS_CLIENT_SECRET environment variables.",
            }

        d = 0.002  # roughly a 200-400m box around the point
        bbox = [lon - d, lat - d, lon + d, lat + d]

        end_date = datetime.utcnow().date()
        start_date = end_date - timedelta(days=30)

        # NDVI = (near-infrared - red) / (near-infrared + red).
        # B08 = Sentinel-2's near-infrared band, B04 = its red band.
        # dataMask must be declared as its own OUTPUT (not just an input) --
        # the Statistical API uses it to know which pixels are valid vs.
        # cloud-masked when computing the aggregate statistics.
        evalscript = """
        //VERSION=3
        function setup() {
          return {
            input: [{bands: ["B04", "B08", "dataMask"]}],
            output: [
              {id: "ndvi", bands: 1, sampleType: "FLOAT32"},
              {id: "dataMask", bands: 1}
            ]
          };
        }
        function evaluatePixel(sample) {
          let ndvi = (sample.B08 - sample.B04) / (sample.B08 + sample.B04);
          return {
            ndvi: [ndvi],
            dataMask: [sample.dataMask]
          };
        }
        """

        request_body = {
            "input": {
                "bounds": {
                    "bbox": bbox,
                    "properties": {"crs": "http://www.opengis.net/def/crs/OGC/1.3/CRS84"},
                },
                "data": [{
                    "type": "sentinel-2-l2a",
                    "dataFilter": {"maxCloudCoverage": 40},
                }],
            },
            "aggregation": {
                "timeRange": {
                    "from": f"{start_date}T00:00:00Z",
                    "to": f"{end_date}T23:59:59Z",
                },
                "aggregationInterval": {"of": "P30D"},
                "evalscript": evalscript,
                "resx": 10,
                "resy": 10,
            },
        }

        resp = requests.post(
            "https://sh.dataspace.copernicus.eu/api/v1/statistics",
            headers={"Authorization": f"Bearer {token}"},
            json=request_body,
            timeout=TIMEOUT,
        )
        if not resp.ok:
            # Surface the SERVER's actual explanation, not just "400 Bad Request" --
            # Sentinel Hub returns a specific reason in the response body that a
            # generic raise_for_status() would otherwise throw away.
            return {
                "source": "Copernicus Sentinel-2",
                "status": "error",
                "error": f"HTTP {resp.status_code}: {resp.text[:500]}",
            }
        data = resp.json()

        # Response shape: data["data"][0]["outputs"]["ndvi"]["bands"]["B0"]["stats"]
        intervals = data.get("data", [])
        if not intervals:
            return {"source": "Copernicus Sentinel-2", "status": "error",
                     "error": "No cloud-free imagery in the last 30 days for this point."}

        stats = intervals[0]["outputs"]["ndvi"]["bands"]["B0"]["stats"]
        ndvi_mean = stats.get("mean")

        return {
            "source": "Copernicus Sentinel-2",
            "status": "ok",
            "ndvi": round(ndvi_mean, 3) if ndvi_mean is not None else None,
            "period": f"{start_date} to {end_date}",
        }
    except Exception as e:
        return {"source": "Copernicus Sentinel-2", "status": "error", "error": str(e)}


def fetch_farm_data(lat: float, lon: float) -> dict:
    """Fires all data source calls IN PARALLEL and merges results.
    This is the function your API endpoint calls when a farmer submits
    a location.
    """
    start = time.time()
    tasks = {
        "climate": get_climate_data,
        "soil": get_soil_data,
        "elevation": get_elevation,
        "vegetation": get_vegetation_data,
    }

    results = {}
    with ThreadPoolExecutor(max_workers=len(tasks)) as executor:
        future_to_key = {
            executor.submit(fn, lat, lon): key for key, fn in tasks.items()
        }
        for future in as_completed(future_to_key):
            key = future_to_key[future]
            results[key] = future.result()

    return {
        "location": {"latitude": lat, "longitude": lon},
        "fetched_in_seconds": round(time.time() - start, 2),
        "data": results,
    }


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Usage: python orchestrator.py <latitude> <longitude>")
        print("Example: python orchestrator.py 30.3398 76.3869")
        sys.exit(1)

    lat, lon = float(sys.argv[1]), float(sys.argv[2])
    farm_data = fetch_farm_data(lat, lon)
    print(json.dumps(farm_data, indent=2))
