# Sprinkler LLM Decision Rules - Spanish Fort, AL

File: SPRINKLER_LLM_RULES.md  
Version: 1.1  
Last Updated: April 2026  
Location: Spanish Fort, Alabama

## Purpose
This document defines what the LLM should output for irrigation decisions, aligned with current AISprinkler runtime expectations.

## 1. Input Data Provided to the LLM

Every call includes a payload equivalent to the runtime request context.

```json
{
  "run_id": "uuid",
  "correlation_id": "uuid",
  "device_id": "uuid",
  "baseline_duration_minutes": 40,
  "weather": {
    "rain_last_24h_mm": 12.4,
    "rain_forecast_next_24h_mm": 8.2,
    "rain_probability_pct": 65.0,
    "temperature_c": 24.1,
    "humidity_pct": 78.0,
    "wind_speed_kmh": 9.3,
    "provider": "open_meteo",
    "is_fallback_provider": false
  },
  "policy_version": "v1.0.0",
  "prompt_version": "prompt.v1.0.0"
}
```

Weather fields represent:
1. Historical observation signal: rain_last_24h_mm.
2. Forecast signals: rain_forecast_next_24h_mm and rain_probability_pct.
3. Additional context: temperature_c, humidity_pct, wind_speed_kmh, provider, is_fallback_provider.

Forecast retrieval and mapping notes:
1. Forecast is retrieved as hourly weather data and then aggregated for the model payload.
2. rain_forecast_next_24h_mm is the sum of forecast rain_mm for the next 24 hours.
3. rain_probability_pct is the maximum forecast precipitation probability in the next 24 hours.
4. These aggregated forecast values are always included in weather when forecast retrieval succeeds.

## 2. Decision Rules (Apply in this order)

1. If rain_last_24h_mm is high, prefer reduce or skip.
2. If rain_forecast_next_24h_mm is high, prefer reduce or skip.
3. If rain_probability_pct is high, do not increase.
4. If observed and forecast rain are both low, keep or slight increase may be used.

Normative policy thresholds:
1. heavy_rain_last_24h_mm: 10
2. high_rain_forecast_next_24h_mm: 8
3. high_rain_probability_pct: 60

Allowed actions:
1. keep
2. reduce
3. skip
4. increase

## 3. Duration Adjustment Guidance

Use baseline_duration_minutes as the anchor.

Guidance:
1. keep: recommended_duration_minutes should usually equal baseline.
2. reduce: recommended_duration_minutes should be less than baseline.
3. increase: recommended_duration_minutes should be greater than baseline.
4. skip: recommended_duration_minutes must be null.

Operational safety bound:
1. Keep recommendations conservative.
2. Final auto-apply in runtime is clamped to policy max adjustment percentage.

## 4. Required Output Format (JSON only)

The response must be valid JSON and include only the schema expected by the system parser.
The JSON below is an example shape and example values, not an exact literal response.
Never copy numbers, rationale text, or provider values from this example.
All output values must be derived from the current input payload.

```json
{
  "recommendation_action": "reduce",
  "recommended_duration_minutes": 32,
  "confidence_score": 0.86,
  "rationale": "Observed rain was high and forecast remains wet, so duration is reduced.",
  "assumptions": [
    "Forecast quality is acceptable for next 24h."
  ],
  "policy_version": "v1.0.0",
  "weather_source_summary": {
    "provider": "open_meteo"
  }
}
```

Field requirements:
1. recommendation_action: exactly one of keep, reduce, skip, increase.
2. recommended_duration_minutes: integer or null. Must be null when recommendation_action is skip.
3. confidence_score: float in range [0.0, 1.0].
4. rationale: short, explicit sentence tied to observed and forecast weather inputs.
5. assumptions: array of strings (may be empty).
6. policy_version: string, should match current policy when provided.
7. weather_source_summary: object that includes provider.

Variability expectations:
1. recommendation_action, recommended_duration_minutes, confidence_score, rationale, and assumptions should vary per run based on input weather and baseline.
2. policy_version should reflect current runtime policy value.
3. weather_source_summary.provider should reflect the provider used for that run.

Anti-copy requirements:
1. Do not repeat literal values from this document's JSON example.
2. If the input weather is dry (low observed rain and low forecast rain/probability), rationale must not claim heavy rain.
3. If recommendation_action is keep and baseline_duration_minutes is N, recommended_duration_minutes should normally be N.
4. If recommendation_action is skip, recommended_duration_minutes must be null.

Do not output fields such as decision, adjusted_duration_minutes, confidence (0-100), or rules_triggered because they are not consumed by the current system parser.

## 5. Additional Guidelines

1. Be conservative when uncertainty is high.
2. Never invent missing weather values.
3. If weather input is incomplete or unclear, prefer skip or cautious reduce with lower confidence.
4. Return JSON only, with no extra prose.