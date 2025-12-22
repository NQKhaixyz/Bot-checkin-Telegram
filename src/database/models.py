"""Database models for Telegram Attendance Bot."""

from datetime import datetime
from enum import Enum
from typing import List, Optional

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
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
    created_locations: Mapped[List["Location"]] = relationship(
        "Location", back_populates="creator", lazy="dynamic"
    )

    def __repr__(self) -> str:
        return f"<User(user_id={self.user_id}, full_name='{self.full_name}', role={self.role})>"


class Location(Base):
    """Location model for storing attendance check-in locations."""

    __tablename__ = "locations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    latitude: Mapped[float] = mapped_column(Float, nullable=False)
    longitude: Mapped[float] = mapped_column(Float, nullable=False)
    radius: Mapped[float] = mapped_column(Float, nullable=False, default=100.0)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=func.now(), nullable=False
    )
    created_by: Mapped[Optional[int]] = mapped_column(
        BigInteger, ForeignKey("users.user_id", ondelete="SET NULL"), nullable=True
    )

    # Relationships
    creator: Mapped[Optional["User"]] = relationship(
        "User", back_populates="created_locations"
    )
    attendance_logs: Mapped[List["AttendanceLog"]] = relationship(
        "AttendanceLog", back_populates="location", lazy="dynamic"
    )

    # Constraints
    __table_args__ = (
        CheckConstraint("latitude >= -90 AND latitude <= 90", name="check_latitude"),
        CheckConstraint(
            "longitude >= -180 AND longitude <= 180", name="check_longitude"
        ),
        CheckConstraint("radius > 0", name="check_radius_positive"),
    )

    def __repr__(self) -> str:
        return f"<Location(id={self.id}, name='{self.name}', lat={self.latitude}, lng={self.longitude})>"


class AttendanceLog(Base):
    """Attendance log model for recording user check-ins and check-outs."""

    __tablename__ = "attendance_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("users.user_id", ondelete="CASCADE"), nullable=False
    )
    location_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("locations.id", ondelete="CASCADE"), nullable=False
    )
    type: Mapped[AttendanceType] = mapped_column(String(10), nullable=False)
    timestamp: Mapped[datetime] = mapped_column(
        DateTime, default=func.now(), nullable=False
    )
    user_latitude: Mapped[float] = mapped_column(Float, nullable=False)
    user_longitude: Mapped[float] = mapped_column(Float, nullable=False)
    distance: Mapped[float] = mapped_column(Float, nullable=False)
    is_late: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=func.now(), nullable=False
    )

    # Relationships
    user: Mapped["User"] = relationship("User", back_populates="attendance_logs")
    location: Mapped["Location"] = relationship(
        "Location", back_populates="attendance_logs"
    )

    # Indexes for common queries
    __table_args__ = (
        Index("ix_attendance_logs_user_id", "user_id"),
        Index("ix_attendance_logs_location_id", "location_id"),
        Index("ix_attendance_logs_timestamp", "timestamp"),
        Index("ix_attendance_logs_user_timestamp", "user_id", "timestamp"),
        Index("ix_attendance_logs_type", "type"),
    )

    def __repr__(self) -> str:
        return f"<AttendanceLog(id={self.id}, user_id={self.user_id}, type={self.type}, timestamp={self.timestamp})>"


def init_db(database_url: str) -> sessionmaker:
    """
    Initialize the database and create all tables.

    Args:
        database_url: The database connection URL.

    Returns:
        A sessionmaker instance configured for the database.
    """
    engine = create_engine(database_url, echo=False)
    Base.metadata.create_all(bind=engine)
    return sessionmaker(bind=engine, autocommit=False, autoflush=False)
