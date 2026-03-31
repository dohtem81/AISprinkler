# Prompts and Rules (Normative Policy Source)

This document is the normative source for decision thresholds, action bounds, and confidence gating.

## 1. Policy Version

- policy_version: v1.0.0

All runs must persist this value in recommendation and run artifacts.

## 2. Normative Thresholds

- confidence_auto_apply_threshold: 0.70
- max_auto_adjustment_pct: 20
- heavy_rain_last_24h_mm: 10
- high_rain_forecast_next_24h_mm: 8
- high_rain_probability_pct: 60

## 3. Allowed Actions

- keep: retain baseline duration
- reduce: set duration lower than baseline
- skip: no irrigation for run window
- increase: set duration higher than baseline

## 4. Deterministic Hard Rules

1. If maintenance blackout is active, final action must be skip.
2. If runtime command constraints are violated, clamp to device max and min.
3. Automatic increase or reduce cannot exceed plus or minus max_auto_adjustment_pct.
4. If weather context is stale beyond orchestration freshness limit, fallback to baseline keep.
5. If schema or policy version mismatch occurs, run enters manual_review.

## 5. Decision Rubric (Agent Guidance)

- If rain_last_24h_mm >= heavy_rain_last_24h_mm, prefer reduce or skip.
- If rain_forecast_next_24h_mm >= high_rain_forecast_next_24h_mm, prefer reduce or skip.
- If rain_probability_pct >= high_rain_probability_pct, avoid increase.
- If both observed and forecast rain are low, keep or slight increase may be considered.
- Rationale must cite observed and forecast values used.

## 6. Confidence Gating

- confidence >= confidence_auto_apply_threshold: eligible for auto-apply path
- confidence < confidence_auto_apply_threshold: manual_review path required

Confidence does not bypass hard rules.

## 7. Prompt Stack (Design Text)

### 7.1 System Prompt Template

You are AISprinkler Decision Agent. Optimize water use while respecting policy and deterministic constraints. Return only valid JSON in the required schema. Never propose unsupported action names. Never exceed policy bounds.

### 7.2 Decision Rubric Prompt Template

Use observed rain last 24h and forecast rain next 24h as primary features. Explain recommendation clearly. If evidence is weak or conflicting, lower confidence.

### 7.3 Tool Use Prompt Template

Use only provided tools for schedule, weather, and policy lookup. Do not invent missing values.

### 7.4 Output Schema Prompt Template

Return object with:

- recommendation_action
- recommended_duration_minutes
- confidence_score
- rationale
- assumptions
- policy_version
- weather_source_summary

## 8. Prompt and Rule Versioning

- prompt_version format: prompt.v<major>.<minor>.<patch>
- policy_version format: v<major>.<minor>.<patch>
- Any threshold change requires policy_version bump.
- Any schema field change requires prompt_version bump.

## 9. Cross-Document Contract

All threshold values in other documents must reference this file and must not redefine conflicting numbers.
