-- Grafana weather given-day summary (table)
SELECT
    event_time::date AS day,
    rain_mm_day,
    avg_temperature_c,
    avg_humidity_pct,
    dominant_sky_condition,
    CASE WHEN is_observed THEN 'observed' ELSE 'forecast' END AS data_type
FROM grafana_weather_given_day_v1
WHERE $__timeFilter(event_time)
ORDER BY event_time DESC
LIMIT 1;

-- Grafana weather forecast chart (next 7 days, hourly)
SELECT event_time AS "time", rain_mm AS value, 'rain_mm' AS metric
FROM grafana_weather_next_7d_v1
UNION ALL
SELECT event_time AS "time", temperature_c AS value, 'temperature_c' AS metric
FROM grafana_weather_next_7d_v1
UNION ALL
SELECT event_time AS "time", humidity_pct AS value, 'humidity_pct' AS metric
FROM grafana_weather_next_7d_v1
ORDER BY 1;

-- Grafana weather forecast chart (next 7 days, daily rollup)
SELECT event_time AS "time", rain_mm_day AS value, 'rain_mm_day' AS metric
FROM grafana_weather_next_7d_daily_v1
UNION ALL
SELECT event_time AS "time", avg_temperature_c AS value, 'avg_temperature_c' AS metric
FROM grafana_weather_next_7d_daily_v1
UNION ALL
SELECT event_time AS "time", avg_humidity_pct AS value, 'avg_humidity_pct' AS metric
FROM grafana_weather_next_7d_daily_v1
ORDER BY 1;

-- Grafana weather conditions table (next 7 days)
SELECT
    event_time::date AS day,
    rain_mm_day,
    avg_temperature_c,
    avg_humidity_pct,
    dominant_sky_condition
FROM grafana_weather_next_7d_daily_v1
ORDER BY event_time ASC;

-- Grafana LLM decisions table query
SELECT
    event_time,
    model_name,
    decision,
    confidence_score,
    recommended_duration_minutes,
    rationale_summary,
    correlation_id
FROM grafana_llm_decisions_v1
WHERE $__timeFilter(event_time)
ORDER BY event_time DESC
LIMIT 500;

-- Grafana LLM prompt exchange table query (sent vs received)
SELECT
    created_at AS event_time,
    correlation_id,
    model_name,
    prompt_version,
    policy_version,
    LEFT(prompt_text, 2500) AS sent_prompt,
    LEFT(response_text, 2500) AS received_response
FROM agent_prompt_exchange
WHERE $__timeFilter(created_at)
ORDER BY created_at DESC
LIMIT 200;

-- Grafana schedule timeline view query
SELECT
    schedule_start_local AS "time",
    schedule_end_local AS time_end,
    device_name AS metric,
    state,
    duration_minutes,
    source
FROM grafana_schedule_timeline_v1
WHERE $__timeFilter(schedule_start_local)
ORDER BY schedule_start_local;
