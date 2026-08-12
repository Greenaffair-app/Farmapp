"""
Farm Report Generator
----------------------
Takes the raw JSON from orchestrator.py / api.py (numbers only) and
turns it into a short, plain-language report a farmer can actually
read -- no jargon, no raw data tables.

Requires: pip install anthropic --break-system-packages

You need an Anthropic API key (from console.anthropic.com) set as an
environment variable before this will work:

    Windows (cmd):   set ANTHROPIC_API_KEY=sk-ant-xxxxx
    Mac/Linux:       export ANTHROPIC_API_KEY=sk-ant-xxxxx

Usage:
    python report_generator.py
    (uses the sample data at the bottom as a test)
"""

import json
from anthropic import Anthropic

client = Anthropic()  # reads ANTHROPIC_API_KEY from environment automatically

MODEL = "claude-haiku-4-5-20251001"  # fast + cheap -- right fit for a ₹100 report


def summarize_for_prompt(farm_data: dict) -> dict:
    """Raw API data has 12 months x 6 parameters -- too much to hand the AI
    for a cheap report. This pulls out the handful of numbers that actually
    matter, so the prompt stays short and the API call stays cheap.
    """
    climate = farm_data["data"].get("climate", {})
    soil = farm_data["data"].get("soil", {})
    elevation = farm_data["data"].get("elevation", {})
    location = farm_data.get("location", {})

    summary = {
        "latitude": location.get("latitude"),
        "longitude": location.get("longitude"),
        "annual_avg_temp_c": climate.get("annual_avg_temp_c"),
        "annual_rainfall_mm": climate.get("annual_rainfall_mm"),
        "elevation_m": elevation.get("elevation_m"),
        "soil_ph": soil.get("ph"),
        "soil_organic_carbon": soil.get("organic_carbon_g_per_kg"),
        "soil_texture": {
            "clay_pct": soil.get("clay_pct"),
            "sand_pct": soil.get("sand_pct"),
            "silt_pct": soil.get("silt_pct"),
        },
    }

    # Find hottest/coldest/wettest months if monthly data is present
    if climate.get("monthly_avg_temp_c"):
        temps = {m: v for m, v in climate["monthly_avg_temp_c"].items() if v is not None}
        if temps:
            summary["hottest_month"] = max(temps, key=temps.get)
            summary["coldest_month"] = min(temps, key=temps.get)
    if climate.get("monthly_rainfall_mm"):
        rain = {m: v for m, v in climate["monthly_rainfall_mm"].items() if v is not None}
        if rain:
            summary["wettest_month"] = max(rain, key=rain.get)

    return summary


def generate_basic_report(farm_data: dict, language: str = "English") -> str:
    """Calls Claude to turn the trimmed data into a farmer-readable report."""
    stats = summarize_for_prompt(farm_data)

    prompt = f"""You are helping a farmer understand their land. Below is real
data about their farm's location. Write a short, warm, plain-language report --
no jargon, no bullet-pointed data dumps, write it like you're talking to someone
who has never seen a soil report before.

Farm data (JSON):
{json.dumps(stats, indent=2)}

Structure your report as:
1. A one-line headline about their land (something that would make them want
   to keep reading)
2. Climate in plain words -- what the year generally feels like there
3. Soil in plain words -- is it healthy, what does the pH/carbon level mean
   for growing things, in simple terms
4. One practical planning tip based on the data (e.g. best time to plant,
   water management note)
5. A short closing line that creates curiosity about a deeper analysis
   (pest risk, crop-specific recommendations) without being pushy

Respond entirely in {language}. Keep it under 200 words. Do not mention that
you are an AI or that this came from an API."""

    response = client.messages.create(
        model=MODEL,
        max_tokens=500,
        messages=[{"role": "user", "content": prompt}],
    )
    return response.content[0].text


def generate_complete_report(farm_data: dict, scorecard: dict, language: str = "English") -> dict:
    """Replaces the old two-call approach (generate_structured_report +
    generate_scorecard_report) with ONE call that writes every section at
    once. This fixes a real problem the two-call version had: each call
    only saw part of the picture, so they'd independently land on the same
    standout fact (e.g. "August is the wettest month") and each mention it
    in their own words -- producing visible repetition across the report.
    One call that sees everything can be told explicitly not to repeat
    itself. This also halves the AI cost per report.
    """
    stats = summarize_for_prompt(farm_data)

    constraints_summary = [
        {"parameter": c["label"], "value": c["value"], "unit": c["unit"],
         "ideal_range": f"{c['ideal_low']}–{c['ideal_high']}{c['unit']}"}
        for c in scorecard["top_constraints"]
    ]
    input_saving_summary = [
        {"parameter": p["label"], "value": p["value"], "unit": p["unit"]}
        for p in scorecard["input_saving"][:2]
    ]

    prompt = f"""You are helping a farmer understand a full soil and climate
report for their land, generated for {scorecard.get('farming_type', 'conventional')} farming.

Farm data (JSON):
{json.dumps(stats, indent=2)}

Overall grade: {scorecard['grade']} ({scorecard['overall_score']}/100)

The THREE real constraints on this land (already identified by real
threshold analysis, ranked worst first -- do not second-guess this
ranking, just explain and act on it):
{json.dumps(constraints_summary, indent=2)}

Parameters already performing well (candidates for "don't waste money
here"):
{json.dumps(input_saving_summary, indent=2)}

Respond with ONLY a JSON object (no markdown fences, no preamble) with
exactly these keys:

- "headline": a short, warm headline about their land, under 12 words
- "climate_narrative": 2-3 plain-language sentences about their climate
- "soil_narrative": 2-3 plain-language sentences about soil health, what
  pH/carbon actually mean for growing things
- "region_facts": 2-3 sentences of genuine, general geographic/agricultural
  context for this broad area. Stay general -- do not invent specific
  statistics or numbers you're not confident about.
- "scorecard_summary": 1-2 sentences explaining what the overall grade means
- "constraint_actions": an array of exactly 3 short strings, one per
  constraint above IN THE SAME ORDER, each explaining why it matters and
  one concrete fix -- 1-2 sentences each
- "input_saving_tip": one sentence naming a specific input the farmer can
  SKIP or reduce this season, referencing one of the "performing well"
  parameters above by name
- "planning_tip": one practical, specific sowing-timing recommendation.
  Do NOT default to "plant in the wettest month" -- actually reason about
  whether this soil's texture and drainage can handle monsoon-season
  planting. Clay-heavy or poorly-draining soil in a heavy-rainfall month
  risks waterlogging and root rot; for that combination, recommend winter
  (rabi) sowing after the heaviest rains pass instead, and say why. Only
  recommend monsoon (kharif) sowing when the soil's texture and drainage
  can actually handle that much water. Base this on the real texture and
  rainfall data given above, not a generic assumption.
- "disease_risk_flag": one specific, attention-grabbing sentence naming a
  fungal or bacterial disease RISK FACTOR based on this land's actual
  humidity/temperature/rainfall pattern (for example: sustained high
  humidity combined with warm temperatures during the monsoon months
  favors fungal pathogens like blast or blight; poor drainage plus heat
  favors bacterial wilt). Ground this in the real data given -- reference
  the actual number that creates the risk (e.g. "your August humidity of
  79%..."). Frame this as a genuine risk factor to monitor, NOT a
  diagnosis or a claim that disease is present -- never claim a specific
  disease IS occurring, only that conditions favor it. This should feel
  urgent and specific to their exact data, not generic.
- "closing_hook": one short line creating curiosity about deeper analysis
  (crop-specific diagnosis, pest risk) without being pushy

CRITICAL: every section above appears together on the same report. Do NOT
repeat the same fact, number, or observation in more than one section --
each section must add something the others haven't already said. For
example, if climate_narrative mentions the wettest month, planning_tip
must NOT repeat that same fact -- it should cover a different, specific
action instead.

Respond entirely in {language}. Do not mention that you are an AI or that
this came from an API. Output ONLY the raw JSON object, nothing else."""

    response = client.messages.create(
        model=MODEL,
        max_tokens=900,
        messages=[{"role": "user", "content": prompt}],
    )
    raw_text = response.content[0].text.strip()

    if raw_text.startswith("```"):
        raw_text = raw_text.split("```")[1]
        if raw_text.startswith("json"):
            raw_text = raw_text[4:]
        raw_text = raw_text.strip()

    return json.loads(raw_text)


if __name__ == "__main__":
    # Sample data shaped like what api.py's /farm-report endpoint returns --
    # lets you test this file on its own without running the full API.
    sample_farm_data = {
        "location": {"latitude": 30.3398, "longitude": 76.3869},
        "data": {
            "climate": {
                "annual_avg_temp_c": 24.1,
                "annual_rainfall_mm": 750,
                "monthly_avg_temp_c": {
                    "JAN": 13.5, "FEB": 16.8, "MAR": 22.1, "APR": 28.4,
                    "MAY": 32.6, "JUN": 33.2, "JUL": 30.5, "AUG": 29.8,
                    "SEP": 29.1, "OCT": 25.3, "NOV": 19.6, "DEC": 14.9,
                },
                "monthly_rainfall_mm": {
                    "JAN": 20, "FEB": 18, "MAR": 15, "APR": 8,
                    "MAY": 12, "JUN": 55, "JUL": 180, "AUG": 165,
                    "SEP": 90, "OCT": 15, "NOV": 5, "DEC": 8,
                },
            },
            "soil": {
                "ph": 7.8,
                "organic_carbon_g_per_kg": 4.2,
                "clay_pct": 22, "sand_pct": 45, "silt_pct": 33,
            },
            "elevation": {"elevation_m": 250},
        },
    }

    report = generate_basic_report(sample_farm_data, language="English")
    print(report)
