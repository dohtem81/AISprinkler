# Baseline Schedule – Alabama Best Practices

## 1. Climate Context

Alabama spans USDA hardiness zones 7a through 8b (northern highlands to Gulf coastal plain).

Key characteristics:

- Annual rainfall: 52–65 inches, relatively well distributed across the year
- Temperature range: winters mild (avg low 32–40 °F), summers hot and humid (avg high 88–96 °F)
- Primary drought window: July–August heat stress periods
- Humidity: high year-round, which increases disease pressure when watering is poorly timed

## 2. Dominant Lawn Grass in Alabama

| Grass Type      | Zones         | Notes                                                  |
|-----------------|---------------|--------------------------------------------------------|
| Bermuda grass   | All of Alabama| Most common; high heat tolerance; active May–September |
| Centipede grass | Central/South | Low maintenance; sensitive to over-watering            |
| Zoysia grass    | All           | Drought tolerant; slower growth                        |
| St. Augustine   | South Alabama | High water need; not frost tolerant                    |

The Alabama Cooperative Extension System recommends approximately 1–1.5 inches of combined rainfall + irrigation per week for Bermuda grass during the growing season (May–September).

This schedule targets Bermuda grass as the representative default. Centipede requires 20–30% less duration; St. Augustine may require 10–15% more.

## 3. Best Practices Applied

1. **Early morning watering only** – Scheduled between 05:30 and 06:00 AM. This minimizes fungal disease spread (a critical concern in Alabama's humid climate) and cap evaporation losses before peak afternoon heat.

2. **Never water in the evening** – Wet foliage overnight is the primary driver of turf disease in Alabama.

3. **Deep and infrequent over shallow and frequent** – Watering fewer days per week with longer durations (20–25 min) promotes deeper root growth vs. daily short cycles.

4. **Seasonal reduction in fall and winter** – Bermuda grass goes dormant around October–November. Watering needs drop significantly. Alabama's winter rainfall typically supplies adequate moisture, supplemented only during extended dry spells.

5. **AI agent adjusts around baseline** – The following schedule represents the AI-free fallback. The agent applies weather-context adjustments (observed rainfall, forecast) on top of this foundation.

6. **Watering day pattern** – Monday / Wednesday / Friday spacing provides adequate dry-down time between cycles to reduce disease pressure.

## 4. Seasonal Baseline Schedule

All times are device local time. Device timezone must be set to `America/Chicago` (Alabama is Central Time).

### 4.1 Summer (May 1 – September 30)

Peak evapotranspiration window. Bermuda grass actively growing.

| Day of Week | Day Name  | Start Time | Duration |
|-------------|-----------|------------|----------|
| 0           | Monday    | 05:30      | 25 min   |
| 2           | Wednesday | 05:30      | 25 min   |
| 4           | Friday    | 05:30      | 25 min   |
| 5           | Saturday  | 05:30      | 25 min   |

Weekly total: 100 minutes. Approximate water delivery: ~1.25 inches depending on precipitation rate.

Rationale: Four-day schedule replaces Tuesday/Thursday rest days. Saturday run bridges the weekend dry period. Duration 25 min reflects higher evapotranspiration and more direct delivery to root zone.

### 4.2 Spring (March 1 – April 30)

Active growth resumes. Temperatures rising. Spring rainfall typically adequate but supplemental irrigation starts.

| Day of Week | Day Name  | Start Time | Duration |
|-------------|-----------|------------|----------|
| 0           | Monday    | 06:00      | 15 min   |
| 2           | Wednesday | 06:00      | 15 min   |
| 4           | Friday    | 06:00      | 15 min   |

Weekly total: 45 minutes. Approximate water delivery: ~0.5–0.6 inches.

Rationale: Three-day schedule at lower duration. Spring rain is plentiful in Alabama; the AI agent will frequently reduce or skip based on observed rainfall.

### 4.3 Fall (October 1 – November 30)

Bermuda grass transitioning toward dormancy. Temperatures cooling. Rainfall increasing.

| Day of Week | Day Name  | Start Time | Duration |
|-------------|-----------|------------|----------|
| 0           | Monday    | 06:00      | 15 min   |
| 3           | Thursday  | 06:00      | 15 min   |

Weekly total: 30 minutes. Approximate water delivery: ~0.35 inches.

Rationale: Reduced to two days as growth slows. The AI agent will frequently skip these runs as fall fronts bring regular rainfall.

### 4.4 Winter (December 1 – February 28)

Bermuda grass fully dormant. Irrigation primarily prevents drought stress only during extended dry spells.

| Day of Week | Day Name  | Start Time | Duration |
|-------------|-----------|------------|----------|
| 0           | Monday    | 06:00      | 10 min   |
| 3           | Thursday  | 06:00      | 10 min   |

Weekly total: 20 minutes. Approximate water delivery: ~0.25 inches.

Rationale: Minimal schedule. The AI agent is expected to skip most winter runs when in-period rainfall exceeds 10 mm/week. The schedule remains active so the orchestrator has a safe baseline to fall back to.

## 5. Schedule Summary Table

| Season | Months       | Days/Week | Start   | Duration | Total Min/Week |
|--------|--------------|-----------|---------|----------|----------------|
| Spring | Mar–Apr      | 3         | 06:00   | 15 min   | 45             |
| Summer | May–Sep      | 4         | 05:30   | 25 min   | 100            |
| Fall   | Oct–Nov      | 2         | 06:00   | 15 min   | 30             |
| Winter | Dec–Feb      | 2         | 06:00   | 10 min   | 20             |

## 6. AI Agent Integration Notes

- This baseline is the fallback when confidence is below threshold.
- Agent adjustments are bounded by ±20% of baseline `duration_minutes` per policy.
- A `skip` action overrides the baseline entirely for that run window.
- If weather skip occurs in winter, no increase is triggered the next day.

## 7. Seed Data Reference

SQL seed file: `config/seeds/alabama_baseline_schedule.sql`

That file inserts one representative device and all seasonal schedule rows derived from this document.

## 8. Sources

- Alabama Cooperative Extension System – Water Management for Home Lawns and Landscapes
- NOAA Climate Data for Alabama (statewide averages)
- University of Florida IFAS Extension – Turfgrass Water Requirements (referenced for Bermuda ETc)
