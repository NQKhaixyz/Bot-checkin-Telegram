"""Database package for Telegram Attendance Bot."""

from .models import (
    AttendanceLog,
    AttendanceType,
    Base,
    Location,
    User,
    UserRole,
    UserStatus,
    init_db as _init_db,
)
from .session import get_db, get_db_session, set_session_factory


def init_db(database_url: str) -> None:
    """
    Initialize the database.
    
    Creates all tables and sets up the session factory.
    
    Args:
        database_url: The database connection URL.
    """
    session_factory = _init_db(database_url)
    set_session_factory(session_factory)


__all__ = [
    # Base class
    "Base",
    # Enums
    "UserRole",
    "UserStatus",
    "AttendanceType",
    # Models
    "User",
    "Location",
    "AttendanceLog",
    # Database utilities
    "init_db",
    "get_db_session",
    "get_db",
]
