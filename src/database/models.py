"""Database models for Telegram Attendance Bot with Point System."""

import logging
from datetime import datetime, timedelta
from enum import Enum
from typing import List, Optional

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    text,
    create_engine,
    func,
)
from sqlalchemy.orm import (
    DeclarativeBase,
    Mapped,
    mapped_column,
    relationship,
    sessionmaker,
)


class Base(DeclarativeBase):
    """Base class for all database models."""
    pass


class UserRole(str, Enum):
    """User role enumeration."""
    ADMIN = "admin"
    MEMBER = "member"


class UserStatus(str, Enum):
    """User status enumeration."""
    ACTIVE = "active"
    PENDING = "pending"
    BANNED = "banned"


class AttendanceType(str, Enum):
    """Attendance type enumeration."""
    IN = "IN"
    OUT = "OUT"


class EvidenceStatus(str, Enum):
    """Evidence status enumeration."""
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"


class WarningLevel(str, Enum):
    """Warning level - Mức cảnh báo."""
    NONE = "none"           # Không có cảnh báo
    REMIND = "remind"       # Nhắc nhở
    DISCIPLINE = "discipline"  # Kỷ luật
    OUT = "out"             # OUT


class MeetingType(str, Enum):
    """Meeting type - Loại hoạt động."""
    REGULAR = "regular"     # Họp thường tại C1-101: +5 điểm
    SUPPORT = "support"     # Hỗ trợ diễn giả: +10 điểm
    EVENT = "event"         # Hoạt động ngoại khóa lớn: +15 điểm


# Điểm theo loại hoạt động
MEETING_POINTS = {
    MeetingType.REGULAR: 5,   # Họp thường
    MeetingType.SUPPORT: 10,  # Hỗ trợ diễn giả
    MeetingType.EVENT: 15,    # Hoạt động lớn
}


class User(Base):
    """User model for storing Telegram user information."""

    __tablename__ = "users"

    user_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    full_name: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[UserRole] = mapped_column(
        String(20), default=UserRole.MEMBER, nullable=False
    )
    status: Mapped[UserStatus] = mapped_column(
        String(20), default=UserStatus.PENDING, nullable=False
    )
    warning_level: Mapped[WarningLevel] = mapped_column(
        String(20), default=WarningLevel.NONE, nullable=False
    )
    joined_at: Mapped[datetime] = mapped_column(
        DateTime, default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=func.now(), onupdate=func.now(), nullable=False
    )

    # Relationships
    attendance_logs: Mapped[List["AttendanceLog"]] = relationship(
        "AttendanceLog", back_populates="user", lazy="dynamic"
    )
    points: Mapped[List["PointLog"]] = relationship(
        "PointLog", back_populates="user", lazy="dynamic"
    )
    evidences: Mapped[List["Evidence"]] = relationship(
        "Evidence", back_populates="user", foreign_keys="Evidence.user_id", lazy="dynamic"
    )
    registrations: Mapped[List["MeetingRegistration"]] = relationship(
        "MeetingRegistration", back_populates="user", lazy="dynamic"
    )

    def __repr__(self) -> str:
        return f"<User(user_id={self.user_id}, full_name='{self.full_name}', role={self.role})>"


class Location(Base):
    """Location model - Địa điểm check-in."""
    
    __tablename__ = "locations"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    latitude: Mapped[float] = mapped_column(Float, nullable=False)
    longitude: Mapped[float] = mapped_column(Float, nullable=False)
    radius: Mapped[float] = mapped_column(Float, nullable=False, default=50.0)  # meters
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=func.now(), nullable=False)
    created_by: Mapped[Optional[int]] = mapped_column(
        BigInteger, ForeignKey("users.user_id", ondelete="SET NULL"), nullable=True
    )
    
    # Relationships
    meetings: Mapped[List["Meeting"]] = relationship("Meeting", back_populates="location_ref", lazy="dynamic")
    
    __table_args__ = (
        Index("ix_locations_is_active", "is_active"),
    )


class Meeting(Base):
    """Meeting model - Lịch họp với địa điểm và điểm số."""

    __tablename__ = "meetings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    location: Mapped[str] = mapped_column(String(255), nullable=False)
    # GPS coordinates for geofence check-in (direct on meeting)
    latitude: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    longitude: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    radius: Mapped[float] = mapped_column(Float, nullable=False, default=50.0)  # meters for geofence
    # Deprecated: location_id kept for backward compatibility but no longer used
    location_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("locations.id", ondelete="SET NULL"), nullable=True
    )
    meeting_type: Mapped[MeetingType] = mapped_column(
        String(20), default=MeetingType.REGULAR, nullable=False
    )
    points: Mapped[int] = mapped_column(Integer, nullable=False, default=5)
    meeting_time: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    end_time: Mapped[datetime] = mapped_column(DateTime, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=func.now(), nullable=False
    )
    created_by: Mapped[Optional[int]] = mapped_column(
        BigInteger, ForeignKey("users.user_id", ondelete="SET NULL"), nullable=True
    )
    notified: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    # Relationships
    location_ref: Mapped[Optional["Location"]] = relationship(
        "Location", back_populates="meetings"
    )
    attendance_logs: Mapped[List["AttendanceLog"]] = relationship(
        "AttendanceLog", back_populates="meeting", lazy="dynamic"
    )
    registrations: Mapped[List["MeetingRegistration"]] = relationship(
        "MeetingRegistration", back_populates="meeting", lazy="dynamic"
    )

    __table_args__ = (
        Index("ix_meetings_meeting_time", "meeting_time"),
        Index("ix_meetings_is_active", "is_active"),
        Index("ix_meetings_location_id", "location_id"),
    )

    def __repr__(self) -> str:
        return f"<Meeting(id={self.id}, title='{self.title}', time={self.meeting_time})>"


class MeetingRegistration(Base):
    """Meeting registration - Đăng ký tham gia họp."""

    __tablename__ = "meeting_registrations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("users.user_id", ondelete="CASCADE"), nullable=False
    )
    meeting_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("meetings.id", ondelete="CASCADE"), nullable=False
    )
    registered_at: Mapped[datetime] = mapped_column(
        DateTime, default=func.now(), nullable=False
    )
    attended: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    absence_reason: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    penalized: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    # Relationships
    user: Mapped["User"] = relationship("User", back_populates="registrations")
    meeting: Mapped["Meeting"] = relationship("Meeting", back_populates="registrations")

    __table_args__ = (
        Index("ix_meeting_registrations_user_meeting", "user_id", "meeting_id", unique=True),
    )


class AttendanceLog(Base):
    """Attendance log model for recording user check-ins and check-outs."""

    __tablename__ = "attendance_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("users.user_id", ondelete="CASCADE"), nullable=False
    )
    meeting_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("meetings.id", ondelete="CASCADE"), nullable=False
    )
    type: Mapped[AttendanceType] = mapped_column(String(10), nullable=False)
    timestamp: Mapped[datetime] = mapped_column(
        DateTime, default=func.now(), nullable=False
    )
    duration_minutes: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=func.now(), nullable=False
    )

    # Relationships
    user: Mapped["User"] = relationship("User", back_populates="attendance_logs")
    meeting: Mapped["Meeting"] = relationship("Meeting", back_populates="attendance_logs")

    __table_args__ = (
        Index("ix_attendance_logs_user_id", "user_id"),
        Index("ix_attendance_logs_meeting_id", "meeting_id"),
        Index("ix_attendance_logs_timestamp", "timestamp"),
        Index("ix_attendance_logs_user_meeting", "user_id", "meeting_id"),
    )

    def __repr__(self) -> str:
        return f"<AttendanceLog(id={self.id}, user_id={self.user_id}, type={self.type})>"


class PointLog(Base):
    """Point log model - Lưu lịch sử điểm."""

    __tablename__ = "point_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("users.user_id", ondelete="CASCADE"), nullable=False
    )
    points: Mapped[int] = mapped_column(Integer, nullable=False)
    reason: Mapped[str] = mapped_column(String(255), nullable=False)
    source_type: Mapped[str] = mapped_column(String(50), nullable=False)  # 'meeting', 'evidence', 'penalty', 'absence'
    source_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    month: Mapped[int] = mapped_column(Integer, nullable=False)
    year: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=func.now(), nullable=False
    )

    # Relationships
    user: Mapped["User"] = relationship("User", back_populates="points")

    __table_args__ = (
        Index("ix_point_logs_user_id", "user_id"),
        Index("ix_point_logs_month_year", "month", "year"),
        Index("ix_point_logs_user_month_year", "user_id", "month", "year"),
    )

    def __repr__(self) -> str:
        return f"<PointLog(id={self.id}, user_id={self.user_id}, points={self.points})>"


class Evidence(Base):
    """Evidence model - Minh chứng công việc."""

    __tablename__ = "evidences"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("users.user_id", ondelete="CASCADE"), nullable=False
    )
    description: Mapped[str] = mapped_column(Text, nullable=False)
    photo_file_id: Mapped[str] = mapped_column(String(255), nullable=False)
    requested_points: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[EvidenceStatus] = mapped_column(
        String(20), default=EvidenceStatus.PENDING, nullable=False
    )
    reviewed_by: Mapped[Optional[int]] = mapped_column(
        BigInteger, ForeignKey("users.user_id", ondelete="SET NULL"), nullable=True
    )
    review_reason: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    reviewed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=func.now(), nullable=False
    )

    # Relationships
    user: Mapped["User"] = relationship("User", back_populates="evidences", foreign_keys=[user_id])
    reviewer: Mapped[Optional["User"]] = relationship("User", foreign_keys=[reviewed_by])

    __table_args__ = (
        Index("ix_evidences_user_id", "user_id"),
        Index("ix_evidences_status", "status"),
    )

    def __repr__(self) -> str:
        return f"<Evidence(id={self.id}, user_id={self.user_id}, status={self.status})>"


def init_db(database_url: str) -> sessionmaker:
    """Initialize the database and create all tables."""
    engine = create_engine(database_url, echo=False)
    Base.metadata.create_all(bind=engine)
    _run_schema_migrations(engine)
    return sessionmaker(bind=engine, autocommit=False, autoflush=False)


def _run_schema_migrations(engine) -> None:
    """
    Lightweight, in-place migrations for SQLite.
    
    Adds new columns to existing tables if they are missing.
    """
    logger = logging.getLogger(__name__)
    
    with engine.begin() as conn:
        # Check meetings table for new geofence columns
        existing_cols = {
            row[1] for row in conn.execute(text("PRAGMA table_info(meetings)")).fetchall()
        }
        statements = []
        
        if "latitude" not in existing_cols:
            statements.append("ALTER TABLE meetings ADD COLUMN latitude FLOAT")
        if "longitude" not in existing_cols:
            statements.append("ALTER TABLE meetings ADD COLUMN longitude FLOAT")
        if "radius" not in existing_cols:
            statements.append("ALTER TABLE meetings ADD COLUMN radius FLOAT DEFAULT 50.0")
        if "end_time" not in existing_cols:
            statements.append("ALTER TABLE meetings ADD COLUMN end_time DATETIME")
        
        for stmt in statements:
            conn.execute(text(stmt))
        
        if "radius" not in existing_cols:
            conn.execute(text("UPDATE meetings SET radius = 50.0 WHERE radius IS NULL"))
        if "end_time" not in existing_cols:
            conn.execute(text("UPDATE meetings SET end_time = meeting_time"))
        
        # Attendance logs new column
        att_cols = {
            row[1] for row in conn.execute(text("PRAGMA table_info(attendance_logs)")).fetchall()
        }
        if "duration_minutes" not in att_cols:
            conn.execute(text("ALTER TABLE attendance_logs ADD COLUMN duration_minutes FLOAT"))
        
        if statements:
            logger.info("Applied meeting schema migrations: %s", ", ".join(statements))
