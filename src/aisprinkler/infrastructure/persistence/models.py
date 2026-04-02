"""SQLAlchemy ORM models – infrastructure representation of domain entities.

These models are NOT domain entities.  The persistence adapter maps between them.
"""

from __future__ import annotations

import uuid

from sqlalchemy import (
    Boolean,
    Column,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    Index,
    JSON,
    String,
    Text,
    Time,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import DeclarativeBase, relationship


class Base(DeclarativeBase):
    pass


class DeviceModel(Base):
    __tablename__ = "device"

    id = Column(PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String, nullable=False)
    device_type = Column(String, nullable=False)
    timezone = Column(String, nullable=False)
    location_lat = Column(Float, nullable=False)
    location_lon = Column(Float, nullable=False)
    status = Column(String, nullable=False, default="active")
    created_at = Column(DateTime(timezone=True), nullable=False)
    updated_at = Column(DateTime(timezone=True), nullable=False)

    original_schedules = relationship("OriginalBaselineScheduleModel", back_populates="device")
    current_schedules = relationship("CurrentBaselineScheduleModel", back_populates="device")
    runs = relationship("AdjustmentRunModel", back_populates="device")


class OriginalBaselineScheduleModel(Base):
    __tablename__ = "original_baseline_schedule"

    id = Column(PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    device_id = Column(PG_UUID(as_uuid=True), ForeignKey("device.id"), nullable=False)
    schedule_date = Column(Date, nullable=False)
    grass_type = Column(String)
    start_time = Column(Time, nullable=False)
    duration_minutes = Column(Integer, nullable=False)
    is_active = Column(Boolean, nullable=False, default=True)
    notes = Column(Text)
    source = Column(String, nullable=False, default="seed")
    created_at = Column(DateTime(timezone=True), nullable=False)
    updated_at = Column(DateTime(timezone=True), nullable=False)

    device = relationship("DeviceModel", back_populates="original_schedules")

    __table_args__ = (
        Index("ix_original_baseline_schedule_device_date", "device_id", "schedule_date"),
    )


class CurrentBaselineScheduleModel(Base):
    __tablename__ = "current_baseline_schedule"

    id = Column(PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    device_id = Column(PG_UUID(as_uuid=True), ForeignKey("device.id"), nullable=False)
    original_schedule_id = Column(
        PG_UUID(as_uuid=True),
        ForeignKey("original_baseline_schedule.id"),
        nullable=True,
    )
    schedule_date = Column(Date, nullable=False)
    grass_type = Column(String)
    start_time = Column(Time, nullable=False)
    duration_minutes = Column(Integer, nullable=False)
    is_active = Column(Boolean, nullable=False, default=True)
    notes = Column(Text)
    source = Column(String, nullable=False, default="seed")
    superseded_at = Column(DateTime(timezone=True))
    created_at = Column(DateTime(timezone=True), nullable=False)
    updated_at = Column(DateTime(timezone=True), nullable=False)

    device = relationship("DeviceModel", back_populates="current_schedules")
    original_schedule = relationship("OriginalBaselineScheduleModel")

    __table_args__ = (
        Index(
            "ix_current_baseline_schedule_device_date_visible",
            "device_id",
            "schedule_date",
            "is_active",
            "superseded_at",
        ),
    )


class AdjustmentRunModel(Base):
    __tablename__ = "adjustment_run"

    id = Column(PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    correlation_id = Column(PG_UUID(as_uuid=True), nullable=False, unique=True)
    device_id = Column(PG_UUID(as_uuid=True), ForeignKey("device.id"), nullable=False)
    run_date = Column(Date, nullable=False)
    state = Column(String, nullable=False, default="queued")
    trigger_type = Column(String, nullable=False)
    confidence_threshold = Column(Float, nullable=False)
    started_at = Column(DateTime(timezone=True), nullable=False)
    finished_at = Column(DateTime(timezone=True))
    created_at = Column(DateTime(timezone=True), nullable=False)

    device = relationship("DeviceModel", back_populates="runs")


class AgentPromptExchangeModel(Base):
    __tablename__ = "agent_prompt_exchange"

    id = Column(PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    run_id = Column(PG_UUID(as_uuid=True), ForeignKey("adjustment_run.id"), nullable=False)
    correlation_id = Column(PG_UUID(as_uuid=True), nullable=False, index=True)
    model_name = Column(String, nullable=False)
    model_version = Column(String, nullable=False, default="")
    prompt_version = Column(String, nullable=False)
    policy_version = Column(String, nullable=False)
    prompt_text = Column(Text, nullable=False)
    response_text = Column(Text, nullable=False)
    request_payload = Column(JSON, nullable=False)
    response_payload = Column(JSON, nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False)


class AuditEventModel(Base):
    __tablename__ = "audit_event"

    id = Column(PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    correlation_id = Column(PG_UUID(as_uuid=True), nullable=False, index=True)
    entity_type = Column(String, nullable=False)
    entity_id = Column(PG_UUID(as_uuid=True), nullable=False)
    event_type = Column(String, nullable=False)
    actor = Column(String, nullable=False)
    event_payload = Column(JSON, nullable=False)
    occurred_at = Column(DateTime(timezone=True), nullable=False, index=True)


class WeatherLocationModel(Base):
    """Registry of locations queried for weather, keyed by zipcode."""

    __tablename__ = "weather_location"

    id = Column(PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    zipcode = Column(String(10), nullable=False, unique=True)
    city = Column(String)
    state_code = Column(String(2))
    country_code = Column(String(2), nullable=False, default="US")
    location_lat = Column(Float)
    location_lon = Column(Float)
    created_at = Column(DateTime(timezone=True), nullable=False)
    updated_at = Column(DateTime(timezone=True), nullable=False)

    forecast_hours = relationship("WeatherForecastHourModel", back_populates="location")


class WeatherForecastHourModel(Base):
    """One row per (location, hour, provider) – stores both live forecasts and
    verified historical observations once the forecast window passes."""

    __tablename__ = "weather_forecast_hour"

    id = Column(PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    location_id = Column(
        PG_UUID(as_uuid=True), ForeignKey("weather_location.id"), nullable=False
    )
    # Denormalised date column for efficient daily range queries without truncation
    forecast_date = Column(Date, nullable=False)
    # UTC-anchored timestamp representing the start of the forecast hour
    forecast_hour = Column(DateTime(timezone=True), nullable=False)
    temperature_c = Column(Float)
    feels_like_c = Column(Float)
    humidity_pct = Column(Float)
    # Precipitation totals for the hour
    rain_mm = Column(Float)
    snow_mm = Column(Float)
    rain_probability_pct = Column(Float)
    wind_speed_kmh = Column(Float)
    wind_direction_deg = Column(Integer)
    # Provider-specific condition code (e.g. OWM icon, WMO code)
    weather_code = Column(String)
    weather_description = Column(String)
    # False = still a forecast; True = verified historical observation
    is_observed = Column(Boolean, nullable=False, default=False)
    provider = Column(String, nullable=False)
    fetched_at = Column(DateTime(timezone=True), nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False)

    location = relationship("WeatherLocationModel", back_populates="forecast_hours")

    __table_args__ = (
        # Fast daily lookups: all hours for a location on a given date
        Index("ix_weather_forecast_hour_location_date", "location_id", "forecast_date"),
        # Fast latest-forecast lookup for a single hour
        Index("ix_weather_forecast_hour_location_hour", "location_id", "forecast_hour"),
        # Prevents duplicate rows; use ON CONFLICT on this constraint to upsert
        UniqueConstraint(
            "location_id",
            "forecast_hour",
            "provider",
            name="uq_weather_forecast_hour_location_hour_provider",
        ),
    )
