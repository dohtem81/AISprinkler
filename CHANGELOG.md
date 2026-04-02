# Changelog

All notable changes to this project are documented in this file.

The format is based on Keep a Changelog, and this project aims to follow Semantic Versioning.

## [Unreleased]

- No changes yet.

## [0.1.0] - 2026-04-02

### Added

- Initial AISprinkler package scaffolding, core API, domain/application structure, persistence layer, and test foundations.
- Grafana panel for LLM prompt exchange (sent prompt vs received response).
- Historical utility scripts:
  - `scripts/create_baseline_last30d.py`
  - `scripts/adjust_schedule_last30d.py`
- Runtime loading of LLM policy/rules from `config/SPRINKLER_LLM_RULES.md`.

### Changed

- Weather context collection uses next 7 days of hourly forecast data.
- Weather forecast persistence now overwrites future non-observed forecast rows per provider/location before upsert.
- Dashboard weather query switched from next-24h hourly view to next-7d hourly view.
- Trigger behavior updated to better handle date selection when no baseline exists for the current day.
- Documentation synchronized to current architecture, persistence, observability, and runtime behavior.

### Fixed

- Reduced stale future forecast values after provider refresh by replacing future forecast window during ingest.
- Improved resilience against copied-example or inconsistent LLM outputs via runtime recommendation coercion safeguards.
