"""
Soil & Climate Scorecard
--------------------------
Turns raw farm data into a deterministic score per parameter (not AI
narrative -- real thresholds, so the "top constraints" are trustworthy
and reproducible, not something the model improvises differently each
time).

Each parameter definition includes an ideal range. Score = 100 at the
center of the ideal range, tapering to 0 the further a value sits
outside it. A handful of parameters (wind, solar radiation, elevation)
are informational only -- reported, but not scored, since "ideal" is
context-dependent (they don't count toward the overall grade).

NOTE ON THRESHOLDS: these are reasonable general-purpose agronomic
ranges for row-crop farming, not validated per-crop or per-region
recommendations. Treat them as a first-pass screening signal, the
same spirit as the free snapshot itself -- not a substitute for
Greenaffair's lab-based diagnostic.
"""


def _range_score(value, low, high, hard_low=None, hard_high=None):
    """70 (never higher -- always room to improve) inside [low, high],
    tapering linearly to 0 at hard_low/hard_high."""
    if value is None:
        return None
    if hard_low is None:
        hard_low = low - (high - low) * 0.6
    if hard_high is None:
        hard_high = high + (high - low) * 0.6

    if low <= value <= high:
        return 70
    if value < low:
        if value <= hard_low:
            return 0
        return round(70 * (value - hard_low) / (low - hard_low))
    if value >= hard_high:
        return 0
    return round(70 * (hard_high - value) / (hard_high - high))


def _severity(value, low, high):
    """Continuous, UNCLAMPED distance outside the ideal range, as a fraction
    of the range width. Two parameters can both score 0 (fully clamped) while
    one is barely past the hard limit and the other is catastrophically past
    it -- this is what lets 'top constraints' rank the true worst offenders
    instead of picking arbitrarily among ties."""
    if value is None:
        return 0
    if low <= value <= high:
        return 0
    span = high - low
    if span == 0:
        return 0
    if value < low:
        return (low - value) / span
    return (value - high) / span


# Organic carbon targets differ meaningfully by farming system -- this is
# not a minor tweak, it's a real, sourced difference:
#
# CONVENTIONAL: official ICAR-IISS Soil Health Card standard
#   (source: iiss.res.in/old/eMagazine/v4i1/12.pdf)
#   <0.5% Low | 0.5-0.75% Medium | >0.75% High
#   -- calibrated for synthetic-fertilizer-responsive systems, where
#   purchased inputs (not soil biology) carry most of the fertility load.
#
# ORGANIC: researchers cite >2% OC as the minimum viable threshold to
# START organic farming, with 1.5% cited elsewhere as the general
# "critical threshold for healthy soil" -- organic systems need
# substantially more carbon since fertility comes from biology, not
# synthetic inputs.
#
# NATURAL FARMING (ZBNF / Palekar method): does not target OC numbers
# directly at all. The philosophy holds that soil already contains what's
# needed, and the real lever is microbial activity (Jeevamrit, mulching,
# Waaphasa/soil aeration-moisture balance) -- not input dosing of any
# kind, organic or synthetic. We still show OC as a health indicator
# (farmers benefit from seeing it), using the same elevated organic-style
# threshold as a floor, but recommendations avoid any input-dosing
# language entirely -- see report_generator.py's farming_type prompt.
OC_THRESHOLDS_BY_TYPE = {
    "conventional": (0.75, 5.0, (0.2, None)),
    "organic":      (2.0, 6.0, (0.5, None)),
    "natural":      (2.0, 6.0, (0.5, None)),
}


def get_parameter_defs(farming_type: str = "conventional"):
    """Returns PARAMETER_DEFS with organic-carbon thresholds adjusted for
    the farming system. pH and physical soil properties (CEC, bulk
    density, water retention) stay the same across all three -- soil
    chemistry and physics don't change with farming philosophy, only the
    fertility target and how it's discussed do."""
    oc_low, oc_high, _ = OC_THRESHOLDS_BY_TYPE.get(farming_type, OC_THRESHOLDS_BY_TYPE["conventional"])

    return [
        ("annual_rainfall_mm", "Annual Rainfall", "mm", 600, 1200, True, "climate"),
        ("annual_avg_temp_c", "Avg Temperature", "°C", 18, 30, True, "climate"),
        ("annual_avg_humidity_pct", "Humidity", "%", 40, 70, True, "climate"),
        ("annual_avg_wind_speed_ms", "Wind Speed", "m/s", None, None, False, "climate"),
        ("annual_avg_solar_radiation", "Solar Radiation", "kWh/m²/day", None, None, False, "climate"),
        ("elevation_m", "Elevation", "m", None, None, False, "climate"),
        ("ph", "Soil pH", "", 6.5, 7.0, True, "soil"),  # official: <6.5 acidic, 6.5-7.0 neutral, >7.0 alkaline -- same across all types
        ("organic_carbon_pct", "Organic Carbon", "%", oc_low, oc_high, True, "soil"),
        ("nitrogen_g_per_kg", "Total Nitrogen (informational)", "g/kg", None, None, False, "soil"),
        ("cec_cmol_per_kg", "CEC (Nutrient Holding)", "cmol/kg", 15, 40, True, "soil"),
        ("bulk_density_kg_dm3", "Bulk Density (Compaction)", "g/cm³", 1.0, 1.4, True, "soil"),
        ("water_retention_pct", "Water Retention", "%", 20, 35, True, "soil"),
        ("clay_pct", "Clay Content", "%", None, None, False, "soil"),
        ("sand_pct", "Sand Content", "%", None, None, False, "soil"),
        ("silt_pct", "Silt Content", "%", None, None, False, "soil"),
        ("ndvi", "Vegetation Health (NDVI)", "", 0.5, 1.0, True, "vegetation"),  # live Sentinel-2, standard remote-sensing bands
    ]


def get_custom_hard_bounds(farming_type: str = "conventional"):
    """pH hard bounds are the same across farming types (soil chemistry
    doesn't change). Organic carbon's hard-low floor comes from the same
    per-type table used for its ideal range."""
    _, _, oc_hard_bounds = OC_THRESHOLDS_BY_TYPE.get(farming_type, OC_THRESHOLDS_BY_TYPE["conventional"])
    return {
        "ph": (5.5, 8.5),  # full realistic agricultural pH range
        "organic_carbon_pct": oc_hard_bounds,
    }


def build_scorecard(farm_data: dict, farming_type: str = "conventional") -> dict:
    """Takes the raw orchestrator output and returns:
    - overall_score (0-100, average of all SCORED parameters with data)
    - grade (letter grade)
    - parameters: list of dicts, each with score/status for every parameter
    - top_constraints: the 3 lowest-scoring parameters (the real weak points)
    - input_saving: parameters scoring 85+ (things NOT worth spending on)
    - farming_type: echoed back, since thresholds (esp. organic carbon)
      depend on it
    """
    climate = farm_data["data"].get("climate", {})
    soil = farm_data["data"].get("soil", {})
    elevation_data = farm_data["data"].get("elevation", {})
    vegetation_data = farm_data["data"].get("vegetation", {})

    # Flatten all values into one lookup dict matching PARAMETER_DEFS keys
    oc_g_per_kg = soil.get("organic_carbon_g_per_kg")
    values = {
        "annual_rainfall_mm": climate.get("annual_rainfall_mm"),
        "annual_avg_temp_c": climate.get("annual_avg_temp_c"),
        "annual_avg_humidity_pct": climate.get("annual_avg_humidity_pct"),
        "annual_avg_wind_speed_ms": climate.get("annual_avg_wind_speed_ms"),
        "annual_avg_solar_radiation": climate.get("annual_avg_solar_radiation"),
        "elevation_m": elevation_data.get("elevation_m"),
        "ph": soil.get("ph"),
        "organic_carbon_pct": round(oc_g_per_kg / 10, 2) if oc_g_per_kg is not None else None,
        "nitrogen_g_per_kg": soil.get("nitrogen_g_per_kg"),
        "cec_cmol_per_kg": soil.get("cec_cmol_per_kg"),
        "bulk_density_kg_dm3": soil.get("bulk_density_kg_dm3"),
        "water_retention_pct": soil.get("water_retention_pct"),
        "clay_pct": soil.get("clay_pct"),
        "sand_pct": soil.get("sand_pct"),
        "silt_pct": soil.get("silt_pct"),
        "ndvi": vegetation_data.get("ndvi") if vegetation_data.get("status") == "ok" else None,
    }

    parameter_defs = get_parameter_defs(farming_type)
    custom_hard_bounds = get_custom_hard_bounds(farming_type)

    parameters = []
    for key, label, unit, low, high, is_scored, section in parameter_defs:
        value = values.get(key)
        hard_low, hard_high = custom_hard_bounds.get(key, (None, None))
        score = _range_score(value, low, high, hard_low, hard_high) if (is_scored and value is not None) else None
        severity = _severity(value, low, high) if (is_scored and value is not None) else 0
        parameters.append({
            "key": key, "label": label, "unit": unit, "value": value,
            "ideal_low": low, "ideal_high": high, "scored": is_scored, "score": score,
            "severity": severity, "section": section,
        })

    scored_with_data = [p for p in parameters if p["scored"] and p["score"] is not None]
    overall_score = round(sum(p["score"] for p in scored_with_data) / len(scored_with_data)) \
        if scored_with_data else None

    if overall_score is None:
        grade = "—"
    elif overall_score >= 60:
        grade = "A"
    elif overall_score >= 48:
        grade = "B"
    elif overall_score >= 35:
        grade = "C"
    elif overall_score >= 20:
        grade = "D"
    else:
        grade = "F"

    # Ranked by severity (unclamped), not the clamped 0-100 score -- so when
    # several parameters all bottom out at score=0, the true worst of them
    # (furthest past the hard limit) still comes first, not an arbitrary tie.
    # pH is excluded here specifically -- it always gets its own dedicated
    # card in the report regardless of score, so listing it again as a
    # "top constraint" was pure repetition. It's still fully counted in
    # overall_score above; this only affects which 3 names get called out.
    constraint_candidates = [p for p in scored_with_data if p["key"] != "ph"]
    top_constraints = sorted(constraint_candidates, key=lambda p: -p["severity"])[:3]
    input_saving = [p for p in scored_with_data if p["score"] >= 60]

    return {
        "overall_score": overall_score,
        "grade": grade,
        "farming_type": farming_type,
        "parameters": parameters,
        "top_constraints": top_constraints,
        "input_saving": input_saving,
    }
