# Database Schema Implementation Guide

## Overview

This guide covers the complete database design for the Telegram Attendance Bot, including SQLAlchemy models, relationships, and migration setup.

---

## Prerequisites

- Python 3.10+
- SQLAlchemy 2.0+
- Alembic for migrations

---

## Database Tables

### Entity Relationship Diagram

```
┌─────────────┐       ┌──────────────────┐       ┌─────────────┐
│   users     │       │ attendance_logs  │       │  locations  │
├─────────────┤       ├──────────────────┤       ├─────────────┤
│ user_id (PK)│──┐    │ id (PK)          │    ┌──│ id (PK)     │
│ full_name   │  │    │ user_id (FK)     │────┘  │ name        │
│ role        │  └───>│ location_id (FK) │───────│ latitude    │
│ status      │       │ type             │       │ longitude   │
│ joined_at   │       │ timestamp        │       │ radius      │
│ updated_at  │       │ user_latitude    │       │ is_active   │
└─────────────┘       │ user_longitude   │       │ created_at  │
                      │ distance         │       │ created_by  │
                      │ is_late          │       └─────────────┘
                      │ created_at       │
                      └──────────────────┘
```

---

## Implementation Steps

### Step 1: Create Database Directory Structure

```bash
mkdir -p src/database
touch src/database/__init__.py
touch src/database/models.py
touch src/database/session.py
```

### Step 2: Implement Base Model

**File: `src/database/models.py`**

```python
"""
Database models for Telegram Attendance Bot.

This module defines all SQLAlchemy ORM models for:
- User management (users table)
- Location/office management (locations table)  
- Attendance tracking (attendance_logs table)
"""

from datetime import datetime
from enum import Enum as PyEnum
from typing import Optional, List

from sqlalchemy import (
    Column, Integer, BigInteger, String, Float, Boolean, 
    DateTime, ForeignKey, Enum, Index, CheckConstraint,
    create_engine, text
)
from sqlalchemy.orm import (
    DeclarativeBase, relationship, Mapped, mapped_column,
    sessionmaker
)


class Base(DeclarativeBase):
    """Base class for all database models."""
    pass


# ============================================================
# ENUMS
# ============================================================

class UserRole(str, PyEnum):
    """User role enumeration."""
    ADMIN = "admin"
    MEMBER = "member"


class UserStatus(str, PyEnum):
    """User status enumeration."""
    ACTIVE = "active"
    PENDING = "pending"
    BANNED = "banned"


class AttendanceType(str, PyEnum):
    """Attendance log type enumeration."""
    IN = "IN"    # Check-in (arrival)
    OUT = "OUT"  # Check-out (departure)


# ============================================================
# USER MODEL
# ============================================================

class User(Base):
    """
    User model representing registered employees.
    
    Attributes:
        user_id: Telegram user ID (primary key, unique)
        full_name: Employee's real name
        role: Either 'admin' or 'member'
        status: 'active', 'pending', or 'banned'
        joined_at: Registration timestamp
        updated_at: Last update timestamp
    
    Relationships:
        attendance_logs: All attendance records for this user
        created_locations: Locations created by this admin user
    """
    __tablename__ = "users"
    
    # Primary key - using Telegram's user ID
    user_id: Mapped[int] = mapped_column(
        BigInteger, 
        primary_key=True,
        comment="Telegram user ID"
    )
    
    # User information
    full_name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        comment="Employee's full name"
    )
    
    # Role and status
    role: Mapped[UserRole] = mapped_column(
        Enum(UserRole),
        default=UserRole.MEMBER,
        nullable=False,
        comment="User role: admin or member"
    )
    
    status: Mapped[UserStatus] = mapped_column(
        Enum(UserStatus),
        default=UserStatus.PENDING,
        nullable=False,
        index=True,
        comment="Account status"
    )
    
    # Timestamps
    joined_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        nullable=False,
        comment="Registration timestamp"
    )
    
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False,
        comment="Last update timestamp"
    )
    
    # Relationships
    attendance_logs: Mapped[List["AttendanceLog"]] = relationship(
        "AttendanceLog",
        back_populates="user",
        cascade="all, delete-orphan"
    )
    
    created_locations: Mapped[List["Location"]] = relationship(
        "Location",
        back_populates="creator",
        foreign_keys="Location.created_by"
    )
    
    def __repr__(self) -> str:
        return f"<User(id={self.user_id}, name='{self.full_name}', status={self.status.value})>"
    
    @property
    def is_admin(self) -> bool:
        """Check if user has admin role."""
        return self.role == UserRole.ADMIN
    
    @property
    def is_active(self) -> bool:
        """Check if user account is active."""
        return self.status == UserStatus.ACTIVE


# ============================================================
# LOCATION MODEL
# ============================================================

class Location(Base):
    """
    Location model representing office/workplace locations.
    
    Supports multiple branch offices with individual geofence settings.
    
    Attributes:
        id: Auto-increment primary key
        name: Location name (e.g., "HQ Hanoi")
        latitude: GPS latitude coordinate
        longitude: GPS longitude coordinate
        radius: Allowed radius in meters for check-in
        is_active: Whether location accepts check-ins
        created_at: Creation timestamp
        created_by: Admin user who created this location
    
    Relationships:
        creator: Admin user who created this location
        attendance_logs: All check-ins at this location
    """
    __tablename__ = "locations"
    
    # Primary key
    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        autoincrement=True
    )
    
    # Location details
    name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        comment="Location/office name"
    )
    
    latitude: Mapped[float] = mapped_column(
        Float,
        nullable=False,
        comment="GPS latitude coordinate"
    )
    
    longitude: Mapped[float] = mapped_column(
        Float,
        nullable=False,
        comment="GPS longitude coordinate"
    )
    
    radius: Mapped[int] = mapped_column(
        Integer,
        default=50,
        nullable=False,
        comment="Geofence radius in meters"
    )
    
    # Status
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
        index=True,
        comment="Whether location is active"
    )
    
    # Audit fields
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        nullable=False
    )
    
    created_by: Mapped[Optional[int]] = mapped_column(
        BigInteger,
        ForeignKey("users.user_id", ondelete="SET NULL"),
        nullable=True,
        comment="Admin who created this location"
    )
    
    # Relationships
    creator: Mapped[Optional["User"]] = relationship(
        "User",
        back_populates="created_locations",
        foreign_keys=[created_by]
    )
    
    attendance_logs: Mapped[List["AttendanceLog"]] = relationship(
        "AttendanceLog",
        back_populates="location"
    )
    
    # Constraints
    __table_args__ = (
        CheckConstraint('radius > 0', name='positive_radius'),
        CheckConstraint('latitude >= -90 AND latitude <= 90', name='valid_latitude'),
        CheckConstraint('longitude >= -180 AND longitude <= 180', name='valid_longitude'),
    )
    
    def __repr__(self) -> str:
        return f"<Location(id={self.id}, name='{self.name}', radius={self.radius}m)>"


# ============================================================
# ATTENDANCE LOG MODEL
# ============================================================

class AttendanceLog(Base):
    """
    Attendance log model tracking all check-in/check-out events.
    
    Stores detailed information for audit and anti-cheat purposes.
    
    Attributes:
        id: Auto-increment primary key
        user_id: Reference to user who checked in
        location_id: Reference to office location
        type: 'IN' for check-in, 'OUT' for check-out
        timestamp: Server timestamp when recorded
        user_latitude: User's GPS latitude at check-in
        user_longitude: User's GPS longitude at check-in
        distance: Calculated distance from office (meters)
        is_late: Whether arrival was late
        created_at: Record creation timestamp
    
    Relationships:
        user: The user who made this attendance record
        location: The location where check-in occurred
    """
    __tablename__ = "attendance_logs"
    
    # Primary key
    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        autoincrement=True
    )
    
    # Foreign keys
    user_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("users.user_id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    
    location_id: Mapped[Optional[int]] = mapped_column(
        Integer,
        ForeignKey("locations.id", ondelete="SET NULL"),
        nullable=True,
        index=True
    )
    
    # Attendance type
    type: Mapped[AttendanceType] = mapped_column(
        Enum(AttendanceType),
        nullable=False,
        comment="IN for check-in, OUT for check-out"
    )
    
    # Timestamps
    timestamp: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        index=True,
        comment="Server time when attendance was recorded"
    )
    
    # User location data (for audit)
    user_latitude: Mapped[float] = mapped_column(
        Float,
        nullable=False,
        comment="User's GPS latitude"
    )
    
    user_longitude: Mapped[float] = mapped_column(
        Float,
        nullable=False,
        comment="User's GPS longitude"
    )
    
    # Calculated fields
    distance: Mapped[float] = mapped_column(
        Float,
        nullable=False,
        comment="Distance from office in meters"
    )
    
    is_late: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
        index=True,
        comment="True if check-in was late"
    )
    
    # Audit timestamp
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        nullable=False
    )
    
    # Relationships
    user: Mapped["User"] = relationship(
        "User",
        back_populates="attendance_logs"
    )
    
    location: Mapped[Optional["Location"]] = relationship(
        "Location",
        back_populates="attendance_logs"
    )
    
    # Indexes for common queries
    __table_args__ = (
        Index('ix_attendance_user_date', 'user_id', 'timestamp'),
        Index('ix_attendance_date_type', 'timestamp', 'type'),
    )
    
    def __repr__(self) -> str:
        return f"<AttendanceLog(id={self.id}, user={self.user_id}, type={self.type.value}, time={self.timestamp})>"


# ============================================================
# DATABASE INITIALIZATION
# ============================================================

def init_db(database_url: str) -> sessionmaker:
    """
    Initialize database and return session factory.
    
    Args:
        database_url: SQLAlchemy database URL
        
    Returns:
        sessionmaker: Session factory for creating database sessions
        
    Example:
        >>> SessionLocal = init_db("sqlite:///./attendance.db")
        >>> with SessionLocal() as session:
        ...     users = session.query(User).all()
    """
    engine = create_engine(
        database_url,
        echo=False,  # Set to True for SQL debugging
        pool_pre_ping=True  # Enable connection health checks
    )
    
    # Create all tables
    Base.metadata.create_all(bind=engine)
    
    # Create session factory
    SessionLocal = sessionmaker(
        autocommit=False,
        autoflush=False,
        bind=engine
    )
    
    return SessionLocal
```

### Step 3: Implement Session Management

**File: `src/database/session.py`**

```python
"""
Database session management utilities.

Provides context managers and dependency injection for database sessions.
"""

from contextlib import contextmanager
from typing import Generator
import os

from sqlalchemy.orm import Session

from .models import init_db


# Initialize session factory from environment
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./attendance.db")
SessionLocal = init_db(DATABASE_URL)


@contextmanager
def get_db_session() -> Generator[Session, None, None]:
    """
    Context manager for database sessions.
    
    Automatically handles commit/rollback and session cleanup.
    
    Usage:
        >>> with get_db_session() as db:
        ...     user = db.query(User).first()
        ...     user.status = UserStatus.ACTIVE
        ...     # Auto-commits on exit
    
    Yields:
        Session: SQLAlchemy database session
    """
    session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def get_db() -> Generator[Session, None, None]:
    """
    Dependency injection function for FastAPI-style usage.
    
    Usage with python-telegram-bot:
        >>> async def handler(update, context):
        ...     with get_db_session() as db:
        ...         # Use db session
    
    Yields:
        Session: SQLAlchemy database session
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
```

### Step 4: Create Database Init File

**File: `src/database/__init__.py`**

```python
"""
Database package for Telegram Attendance Bot.

Exports:
    - Models: User, Location, AttendanceLog
    - Enums: UserRole, UserStatus, AttendanceType
    - Session management: get_db_session, SessionLocal
"""

from .models import (
    Base,
    User,
    Location,
    AttendanceLog,
    UserRole,
    UserStatus,
    AttendanceType,
    init_db
)

from .session import (
    get_db_session,
    get_db,
    SessionLocal
)

__all__ = [
    # Base
    "Base",
    # Models
    "User",
    "Location", 
    "AttendanceLog",
    # Enums
    "UserRole",
    "UserStatus",
    "AttendanceType",
    # Session
    "init_db",
    "get_db_session",
    "get_db",
    "SessionLocal",
]
```

---

## Common Database Operations

### User Operations

```python
from src.database import User, UserStatus, UserRole, get_db_session

# Create new user (pending approval)
def create_user(user_id: int, full_name: str) -> User:
    with get_db_session() as db:
        user = User(
            user_id=user_id,
            full_name=full_name,
            role=UserRole.MEMBER,
            status=UserStatus.PENDING
        )
        db.add(user)
        db.flush()
        return user

# Get user by Telegram ID
def get_user(user_id: int) -> User | None:
    with get_db_session() as db:
        return db.query(User).filter(User.user_id == user_id).first()

# Approve pending user
def approve_user(user_id: int) -> bool:
    with get_db_session() as db:
        user = db.query(User).filter(User.user_id == user_id).first()
        if user and user.status == UserStatus.PENDING:
            user.status = UserStatus.ACTIVE
            return True
        return False

# Get all pending users
def get_pending_users() -> list[User]:
    with get_db_session() as db:
        return db.query(User).filter(User.status == UserStatus.PENDING).all()
```

### Location Operations

```python
from src.database import Location, get_db_session

# Create office location
def create_location(
    name: str, 
    latitude: float, 
    longitude: float, 
    radius: int,
    created_by: int
) -> Location:
    with get_db_session() as db:
        location = Location(
            name=name,
            latitude=latitude,
            longitude=longitude,
            radius=radius,
            created_by=created_by
        )
        db.add(location)
        db.flush()
        return location

# Get active locations
def get_active_locations() -> list[Location]:
    with get_db_session() as db:
        return db.query(Location).filter(Location.is_active == True).all()

# Get nearest location to coordinates
def get_nearest_location(lat: float, lon: float) -> Location | None:
    # Implementation in geolocation service
    pass
```

### Attendance Operations

```python
from datetime import datetime, date
from src.database import AttendanceLog, AttendanceType, get_db_session

# Record check-in
def record_checkin(
    user_id: int,
    location_id: int,
    user_lat: float,
    user_lon: float,
    distance: float,
    is_late: bool
) -> AttendanceLog:
    with get_db_session() as db:
        log = AttendanceLog(
            user_id=user_id,
            location_id=location_id,
            type=AttendanceType.IN,
            timestamp=datetime.utcnow(),
            user_latitude=user_lat,
            user_longitude=user_lon,
            distance=distance,
            is_late=is_late
        )
        db.add(log)
        db.flush()
        return log

# Get today's attendance for user
def get_today_attendance(user_id: int) -> list[AttendanceLog]:
    with get_db_session() as db:
        today = date.today()
        return db.query(AttendanceLog).filter(
            AttendanceLog.user_id == user_id,
            func.date(AttendanceLog.timestamp) == today
        ).all()

# Check if user already checked in today
def has_checked_in_today(user_id: int) -> bool:
    with get_db_session() as db:
        today = date.today()
        return db.query(AttendanceLog).filter(
            AttendanceLog.user_id == user_id,
            AttendanceLog.type == AttendanceType.IN,
            func.date(AttendanceLog.timestamp) == today
        ).first() is not None
```

---

## Database Migrations with Alembic

### Setup Alembic

```bash
# Install alembic
pip install alembic

# Initialize alembic in project
cd src/database
alembic init migrations
```

### Configure Alembic

**File: `src/database/migrations/env.py`** (modify)

```python
from src.database.models import Base
target_metadata = Base.metadata
```

### Create Migration

```bash
# Generate migration
alembic revision --autogenerate -m "Initial tables"

# Apply migration
alembic upgrade head
```

---

## Testing Database Models

```python
"""Test file: tests/test_database.py"""

import pytest
from datetime import datetime
from src.database import (
    User, Location, AttendanceLog,
    UserRole, UserStatus, AttendanceType,
    init_db, get_db_session
)

@pytest.fixture
def db_session():
    """Create test database session."""
    SessionLocal = init_db("sqlite:///:memory:")
    session = SessionLocal()
    yield session
    session.close()

def test_create_user(db_session):
    """Test user creation."""
    user = User(
        user_id=123456789,
        full_name="Nguyen Van A",
        role=UserRole.MEMBER,
        status=UserStatus.PENDING
    )
    db_session.add(user)
    db_session.commit()
    
    assert user.user_id == 123456789
    assert user.is_admin == False
    assert user.is_active == False

def test_create_location(db_session):
    """Test location creation with constraints."""
    location = Location(
        name="VP Ha Noi",
        latitude=21.0285,
        longitude=105.8542,
        radius=50
    )
    db_session.add(location)
    db_session.commit()
    
    assert location.id is not None
    assert location.is_active == True

def test_attendance_log(db_session):
    """Test attendance logging."""
    # Create user first
    user = User(user_id=111, full_name="Test", status=UserStatus.ACTIVE)
    db_session.add(user)
    
    # Create location
    location = Location(name="Test Office", latitude=21.0, longitude=105.0, radius=50)
    db_session.add(location)
    db_session.commit()
    
    # Create attendance log
    log = AttendanceLog(
        user_id=user.user_id,
        location_id=location.id,
        type=AttendanceType.IN,
        timestamp=datetime.utcnow(),
        user_latitude=21.0001,
        user_longitude=105.0001,
        distance=15.5,
        is_late=False
    )
    db_session.add(log)
    db_session.commit()
    
    assert log.id is not None
    assert log.user.full_name == "Test"
```

---

## Verification Checklist

Before proceeding to the next blueprint, verify:

- [ ] `src/database/models.py` created with all three models
- [ ] `src/database/session.py` created with session management
- [ ] `src/database/__init__.py` exports all necessary items
- [ ] Database can be initialized without errors
- [ ] All model relationships work correctly
- [ ] Constraints (radius > 0, valid coordinates) are enforced

---

## Next Steps

Proceed to `02_BOT_CORE.md` to implement the core bot structure.
