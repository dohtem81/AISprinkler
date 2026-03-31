-- =============================================================================
-- Alabama Baseline Irrigation Schedule – Seed Data
-- =============================================================================
-- Source of schedule values: docs/BASELINE_SCHEDULE_ALABAMA.md
-- Policy version: v1.0.0
-- Grass type: Bermuda (most common in Alabama; adjust duration for other types)
-- Timezone: America/Chicago (Alabama is Central Time)
--
-- day_of_week convention: 0=Monday … 6=Sunday (Python datetime.weekday())
--
-- Seasonal ranges:
--   spring  : effective_month_start=3,  effective_month_end=4
--   summer  : effective_month_start=5,  effective_month_end=9
--   fall    : effective_month_start=10, effective_month_end=11
--   winter  : effective_month_start=12, effective_month_end=2  (year-wrap)
--
-- The orchestrator identifies the active seasonal block for the run date
-- and selects rows where:
--   - season_code matches OR season_code = 'all'
--   - current month is inside [effective_month_start, effective_month_end]
--     (year-wrap: month >= start OR month <= end when end < start)
-- =============================================================================

BEGIN;

-- ---------------------------------------------------------------------------
-- 1. Representative device (Alabama, central location – Montgomery area)
--    Replace this row or ON CONFLICT DO NOTHING if device already exists.
-- ---------------------------------------------------------------------------
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

-- ---------------------------------------------------------------------------
-- 2. SUMMER schedule (May 1 – September 30)
--    Mon / Wed / Fri / Sat  |  05:30  |  25 min
--    Rationale: Peak evapotranspiration; Bermuda in full growth; four-day
--    spacing with Saturday bridge prevents excess soil dry-down.
-- ---------------------------------------------------------------------------
INSERT INTO baseline_schedule (
    id, device_id,
    day_of_week, season_code, effective_month_start, effective_month_end,
    grass_type, start_time, duration_minutes, is_active, notes,
    created_at, updated_at
) VALUES
    -- Monday
    (gen_random_uuid(), '00000000-0000-0000-0000-000000000001',
     0, 'summer', 5, 9,
     'bermuda', '05:30', 25, true,
     'Summer Mon – peak evapotranspiration window',
     now(), now()),
    -- Wednesday
    (gen_random_uuid(), '00000000-0000-0000-0000-000000000001',
     2, 'summer', 5, 9,
     'bermuda', '05:30', 25, true,
     'Summer Wed – mid-week cycle',
     now(), now()),
    -- Friday
    (gen_random_uuid(), '00000000-0000-0000-0000-000000000001',
     4, 'summer', 5, 9,
     'bermuda', '05:30', 25, true,
     'Summer Fri – end of workweek cycle',
     now(), now()),
    -- Saturday
    (gen_random_uuid(), '00000000-0000-0000-0000-000000000001',
     5, 'summer', 5, 9,
     'bermuda', '05:30', 25, true,
     'Summer Sat – weekend bridge; prevents 72-h dry gap',
     now(), now());

-- ---------------------------------------------------------------------------
-- 3. SPRING schedule (March 1 – April 30)
--    Mon / Wed / Fri  |  06:00  |  15 min
--    Rationale: Growth resumes; spring rainfall abundant; supplemental only.
--    AI agent expected to reduce/skip frequently due to Alabama spring rains.
-- ---------------------------------------------------------------------------
INSERT INTO baseline_schedule (
    id, device_id,
    day_of_week, season_code, effective_month_start, effective_month_end,
    grass_type, start_time, duration_minutes, is_active, notes,
    created_at, updated_at
) VALUES
    -- Monday
    (gen_random_uuid(), '00000000-0000-0000-0000-000000000001',
     0, 'spring', 3, 4,
     'bermuda', '06:00', 15, true,
     'Spring Mon – supplemental; AI will skip on rainy weeks',
     now(), now()),
    -- Wednesday
    (gen_random_uuid(), '00000000-0000-0000-0000-000000000001',
     2, 'spring', 3, 4,
     'bermuda', '06:00', 15, true,
     'Spring Wed',
     now(), now()),
    -- Friday
    (gen_random_uuid(), '00000000-0000-0000-0000-000000000001',
     4, 'spring', 3, 4,
     'bermuda', '06:00', 15, true,
     'Spring Fri',
     now(), now());

-- ---------------------------------------------------------------------------
-- 4. FALL schedule (October 1 – November 30)
--    Mon / Thu  |  06:00  |  15 min
--    Rationale: Bermuda transitioning to dormancy; reduce to two-day cycle.
--    Cooler temps and autumn fronts reduce supplemental irrigation need.
-- ---------------------------------------------------------------------------
INSERT INTO baseline_schedule (
    id, device_id,
    day_of_week, season_code, effective_month_start, effective_month_end,
    grass_type, start_time, duration_minutes, is_active, notes,
    created_at, updated_at
) VALUES
    -- Monday
    (gen_random_uuid(), '00000000-0000-0000-0000-000000000001',
     0, 'fall', 10, 11,
     'bermuda', '06:00', 15, true,
     'Fall Mon – reduced schedule; Bermuda slowing growth',
     now(), now()),
    -- Thursday
    (gen_random_uuid(), '00000000-0000-0000-0000-000000000001',
     3, 'fall', 10, 11,
     'bermuda', '06:00', 15, true,
     'Fall Thu',
     now(), now());

-- ---------------------------------------------------------------------------
-- 5. WINTER schedule (December 1 – February 28/29)
--    Mon / Thu  |  06:00  |  10 min
--    Rationale: Bermuda fully dormant. Minimal supplemental irrigation only
--    during extended dry spells (> 2 weeks no rainfall).
--    effective_month_end=2 with effective_month_start=12 signals year-wrap.
-- ---------------------------------------------------------------------------
INSERT INTO baseline_schedule (
    id, device_id,
    day_of_week, season_code, effective_month_start, effective_month_end,
    grass_type, start_time, duration_minutes, is_active, notes,
    created_at, updated_at
) VALUES
    -- Monday
    (gen_random_uuid(), '00000000-0000-0000-0000-000000000001',
     0, 'winter', 12, 2,
     'bermuda', '06:00', 10, true,
     'Winter Mon – dormant; AI expected to skip most weeks',
     now(), now()),
    -- Thursday
    (gen_random_uuid(), '00000000-0000-0000-0000-000000000001',
     3, 'winter', 12, 2,
     'bermuda', '06:00', 10, true,
     'Winter Thu – dormant fallback only',
     now(), now());

COMMIT;

-- =============================================================================
-- Verification query – run after seeding to inspect the full schedule matrix
-- =============================================================================
-- SELECT
--     season_code,
--     effective_month_start AS month_start,
--     effective_month_end   AS month_end,
--     CASE day_of_week
--         WHEN 0 THEN 'Monday'
--         WHEN 1 THEN 'Tuesday'
--         WHEN 2 THEN 'Wednesday'
--         WHEN 3 THEN 'Thursday'
--         WHEN 4 THEN 'Friday'
--         WHEN 5 THEN 'Saturday'
--         WHEN 6 THEN 'Sunday'
--     END                   AS day_name,
--     start_time,
--     duration_minutes,
--     is_active,
--     notes
-- FROM baseline_schedule
-- WHERE device_id = '00000000-0000-0000-0000-000000000001'
-- ORDER BY
--     effective_month_start,
--     day_of_week;
