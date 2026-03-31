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
    JSON,
    SmallInteger,
    String,
    Text,
    Time,
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

    schedules = relationship("BaselineScheduleModel", back_populates="device")
    runs = relationship("AdjustmentRunModel", back_populates="device")


class BaselineScheduleModel(Base):
    __tablename__ = "baseline_schedule"

    id = Column(PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    device_id = Column(PG_UUID(as_uuid=True), ForeignKey("device.id"), nullable=False)
    day_of_week = Column(SmallInteger, nullable=False)
    season_code = Column(String, nullable=False, default="all")
    effective_month_start = Column(SmallInteger, nullable=False, default=1)
    effective_month_end = Column(SmallInteger, nullable=False, default=12)
    grass_type = Column(String)
    start_time = Column(Time, nullable=False)
    duration_minutes = Column(Integer, nullable=False)
    is_active = Column(Boolean, nullable=False, default=True)
    notes = Column(Text)
    created_at = Column(DateTime(timezone=True), nullable=False)
    updated_at = Column(DateTime(timezone=True), nullable=False)

    device = relationship("DeviceModel", back_populates="schedules")


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
