"""
Configuration module for Telegram Attendance Bot.

Loads configuration from environment variables with sensible defaults.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import List, Optional

from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()


def _parse_bool(value: str) -> bool:
    """Parse string to boolean."""
    return value.lower() in ("true", "1", "yes", "on")


def _parse_int_list(value: str) -> List[int]:
    """Parse comma-separated string to list of integers."""
    if not value or not value.strip():
        return []
    return [int(x.strip()) for x in value.split(",") if x.strip()]


@dataclass
class BotConfig:
    """Telegram bot configuration."""
    
    token: str = field(default_factory=lambda: os.getenv("TELEGRAM_BOT_TOKEN", ""))
    
    def __post_init__(self) -> None:
        if not self.token:
            raise ValueError("TELEGRAM_BOT_TOKEN is required")


@dataclass
class DatabaseConfig:
    """Database configuration."""
    
    url: str = field(default_factory=lambda: os.getenv("DATABASE_URL", "sqlite:///./attendance.db"))
    echo: bool = field(default_factory=lambda: _parse_bool(os.getenv("DATABASE_ECHO", "false")))
    
    def __post_init__(self) -> None:
        if not self.url:
            raise ValueError("DATABASE_URL is required")


@dataclass
class AttendanceConfig:
    """Attendance rules configuration."""
    
    work_start_hour: int = field(default_factory=lambda: int(os.getenv("WORK_START_HOUR", "9")))
    work_start_minute: int = field(default_factory=lambda: int(os.getenv("WORK_START_MINUTE", "0")))
    late_threshold_minutes: int = field(default_factory=lambda: int(os.getenv("LATE_THRESHOLD_MINUTES", "15")))
    geofence_default_radius: float = field(default_factory=lambda: float(os.getenv("GEOFENCE_DEFAULT_RADIUS", "50")))
    max_location_age_seconds: int = field(default_factory=lambda: int(os.getenv("MAX_LOCATION_AGE_SECONDS", "60")))
    
    def __post_init__(self) -> None:
        if not 0 <= self.work_start_hour <= 23:
            raise ValueError("WORK_START_HOUR must be between 0 and 23")
        if not 0 <= self.work_start_minute <= 59:
            raise ValueError("WORK_START_MINUTE must be between 0 and 59")
        if self.late_threshold_minutes < 0:
            raise ValueError("LATE_THRESHOLD_MINUTES must be non-negative")
        if self.geofence_default_radius <= 0:
            raise ValueError("GEOFENCE_DEFAULT_RADIUS must be positive")
        if self.max_location_age_seconds <= 0:
            raise ValueError("MAX_LOCATION_AGE_SECONDS must be positive")


@dataclass
class AdminConfig:
    """Admin configuration."""
    
    super_admin_ids: List[int] = field(
        default_factory=lambda: _parse_int_list(os.getenv("ADMIN_USER_IDS", ""))
    )
    
    def is_super_admin(self, user_id: int) -> bool:
        """Check if user is a super admin."""
        return user_id in self.super_admin_ids


@dataclass
class TimezoneConfig:
    """Timezone configuration."""
    
    timezone: str = field(default_factory=lambda: os.getenv("TIMEZONE", "Asia/Ho_Chi_Minh"))
    
    def __post_init__(self) -> None:
        import pytz
        try:
            pytz.timezone(self.timezone)
        except pytz.UnknownTimeZoneError:
            raise ValueError(f"Unknown timezone: {self.timezone}")


@dataclass
class Config:
    """Main configuration class combining all config sections."""
    
    bot: BotConfig = field(default_factory=BotConfig)
    database: DatabaseConfig = field(default_factory=DatabaseConfig)
    attendance: AttendanceConfig = field(default_factory=AttendanceConfig)
    admin: AdminConfig = field(default_factory=AdminConfig)
    timezone: TimezoneConfig = field(default_factory=TimezoneConfig)
    
    @classmethod
    def load(cls) -> Config:
        """Load configuration from environment variables."""
        return cls()
    
    def validate(self) -> None:
        """Validate all configuration sections."""
        # Validation is done in __post_init__ of each config class
        # This method can be used for cross-section validation if needed
        pass


# Singleton instance for easy access
_config: Optional[Config] = None


def get_config() -> Config:
    """Get the configuration singleton."""
    global _config
    if _config is None:
        _config = Config.load()
    return _config


def reload_config() -> Config:
    """Reload configuration from environment variables."""
    global _config
    load_dotenv(override=True)
    _config = Config.load()
    return _config


# Global config instance for easy import
config = get_config()
