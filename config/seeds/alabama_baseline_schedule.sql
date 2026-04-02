-- =============================================================================
-- Alabama Baseline Irrigation Schedule – Dated Seed Data
-- =============================================================================
-- Source of schedule values: docs/BASELINE_SCHEDULE_ALABAMA.md
-- Policy version: v1.0.0
-- Grass type: Bermuda (most common in Alabama; adjust duration for other types)
-- Timezone: America/Chicago (Alabama is Central Time)
--
-- This seed populates the next 7 days of both:
--   - original_baseline_schedule
--   - current_baseline_schedule
--
-- The seed is non-destructive:
--   - original rows are inserted only when the same date/time slot is missing
--   - current rows are inserted only when there is no active visible row
--
-- In production, credentials and identifiers must come from secrets rather than
-- repository-managed defaults.
-- =============================================================================

BEGIN;

CREATE EXTENSION IF NOT EXISTS pgcrypto;

INSERT INTO device (
    id,
    name,
    device_type,
    timezone,
    location_lat,
    location_lon,
    status,
    created_at,
    updated_at
)
VALUES (
    '00000000-0000-0000-0000-000000000001',
    'Primary Lawn – Alabama',
    'generic',
    'America/Chicago',
    32.3617,
    -86.2792,
    'active',
    now(),
    now()
)
ON CONFLICT (id) DO NOTHING;

WITH day_window AS (
    SELECT generate_series(current_date, current_date + 6, interval '1 day')::date AS schedule_date
),
season_templates AS (
    SELECT 'spring'::text AS season_code, 0 AS day_of_week, '06:00'::time AS start_time, 15 AS duration_minutes,
           'Spring Mon – supplemental; AI may skip on rainy weeks'::text AS notes
    UNION ALL SELECT 'spring', 2, '06:00'::time, 15, 'Spring Wed'
    UNION ALL SELECT 'spring', 4, '06:00'::time, 15, 'Spring Fri'
    UNION ALL SELECT 'summer', 0, '05:30'::time, 25, 'Summer Mon – peak evapotranspiration window'
    UNION ALL SELECT 'summer', 2, '05:30'::time, 25, 'Summer Wed – mid-week cycle'
    UNION ALL SELECT 'summer', 4, '05:30'::time, 25, 'Summer Fri – end of workweek cycle'
    UNION ALL SELECT 'summer', 5, '05:30'::time, 25, 'Summer Sat – weekend bridge; prevents 72-h dry gap'
    UNION ALL SELECT 'fall', 0, '06:00'::time, 15, 'Fall Mon – reduced schedule; Bermuda slowing growth'
    UNION ALL SELECT 'fall', 3, '06:00'::time, 15, 'Fall Thu'
    UNION ALL SELECT 'winter', 0, '06:00'::time, 10, 'Winter Mon – dormant; AI expected to skip most weeks'
    UNION ALL SELECT 'winter', 3, '06:00'::time, 10, 'Winter Thu – dormant fallback only'
),
resolved_schedule AS (
    SELECT
        d.schedule_date,
        'bermuda'::text AS grass_type,
        t.start_time,
        t.duration_minutes,
        t.notes
    FROM day_window d
    JOIN season_templates t
      ON t.day_of_week = EXTRACT(ISODOW FROM d.schedule_date)::int - 1
     AND t.season_code = CASE
         WHEN EXTRACT(MONTH FROM d.schedule_date)::int IN (3, 4) THEN 'spring'
         WHEN EXTRACT(MONTH FROM d.schedule_date)::int BETWEEN 5 AND 9 THEN 'summer'
         WHEN EXTRACT(MONTH FROM d.schedule_date)::int IN (10, 11) THEN 'fall'
         ELSE 'winter'
     END
),
inserted_original AS (
    INSERT INTO original_baseline_schedule (
        id,
        device_id,
        schedule_date,
        grass_type,
        start_time,
        duration_minutes,
        is_active,
        notes,
        source,
        created_at,
        updated_at
    )
    SELECT
        gen_random_uuid(),
        '00000000-0000-0000-0000-000000000001'::uuid,
        rs.schedule_date,
        rs.grass_type,
        rs.start_time,
        rs.duration_minutes,
        true,
        rs.notes,
        'manual_seed',
        now(),
        now()
    FROM resolved_schedule rs
    WHERE NOT EXISTS (
        SELECT 1
        FROM original_baseline_schedule obs
        WHERE obs.device_id = '00000000-0000-0000-0000-000000000001'::uuid
          AND obs.schedule_date = rs.schedule_date
          AND obs.start_time = rs.start_time
    )
    RETURNING id, schedule_date, start_time
),
all_original AS (
    SELECT id, schedule_date, start_time
    FROM original_baseline_schedule
    WHERE device_id = '00000000-0000-0000-0000-000000000001'::uuid
      AND schedule_date BETWEEN current_date AND current_date + 6
)
INSERT INTO current_baseline_schedule (
    id,
    device_id,
    original_schedule_id,
    schedule_date,
    grass_type,
    start_time,
    duration_minutes,
    is_active,
    notes,
    source,
    superseded_at,
    created_at,
    updated_at
)
SELECT
    gen_random_uuid(),
    '00000000-0000-0000-0000-000000000001'::uuid,
    ao.id,
    rs.schedule_date,
    rs.grass_type,
    rs.start_time,
    rs.duration_minutes,
    true,
    rs.notes,
    'manual_seed',
    NULL,
    now(),
    now()
FROM resolved_schedule rs
JOIN all_original ao
  ON ao.schedule_date = rs.schedule_date
 AND ao.start_time = rs.start_time
WHERE NOT EXISTS (
    SELECT 1
    FROM current_baseline_schedule cbs
    WHERE cbs.device_id = '00000000-0000-0000-0000-000000000001'::uuid
      AND cbs.schedule_date = rs.schedule_date
      AND cbs.start_time = rs.start_time
      AND cbs.is_active = true
      AND cbs.superseded_at IS NULL
);

COMMIT;

-- =============================================================================
-- Verification query – run after seeding to inspect the visible week-ahead plan
-- =============================================================================
-- SELECT schedule_date, start_time, duration_minutes, notes, source
-- FROM current_baseline_schedule
-- WHERE device_id = '00000000-0000-0000-0000-000000000001'
--   AND is_active = true
--   AND superseded_at IS NULL
-- ORDER BY schedule_date, start_time;
