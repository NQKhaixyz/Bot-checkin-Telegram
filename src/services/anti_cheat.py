"""
Anti-cheat service for Telegram Attendance Bot.

Provides validation and fraud detection for location-based attendance submissions.
"""

from __future__ import annotations

import logging
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Dict, List, Optional

import pytz
from telegram import Message

from src.config import get_config

logger = logging.getLogger(__name__)


@dataclass
class ValidationResult:
    """Result of a validation check."""
    
    is_valid: bool
    error_message: str = ""
    error_code: str = ""
    details: Optional[Dict] = field(default=None)


class AntiCheatService:
    """Service for detecting and preventing attendance fraud."""
    
    _rate_limit_cache: Dict[int, List[datetime]] = defaultdict(list)
    MAX_ATTEMPTS_PER_MINUTE = 3
    
    @staticmethod
    def get_timezone() -> pytz.BaseTzInfo:
        """Get the configured timezone."""
        config = get_config()
        return pytz.timezone(config.timezone.timezone)
    
    @staticmethod
    def validate_location_message(message: Message) -> ValidationResult:
        """
        Run all validation checks on a location message.
        
        Returns the first failure encountered, or success if all checks pass.
        """
        # Check for forwarded message
        result = AntiCheatService.check_forwarded_message(message)
        if not result.is_valid:
            return result
        
        # Check message timestamp
        result = AntiCheatService.check_message_timestamp(message)
        if not result.is_valid:
            return result
        
        # Check rate limit
        result = AntiCheatService.check_rate_limit(message.from_user.id)
        if not result.is_valid:
            return result
        
        # Check live location (informational)
        AntiCheatService.check_live_location(message)
        
        return ValidationResult(is_valid=True)
    
    @staticmethod
    def check_forwarded_message(message: Message) -> ValidationResult:
        """
        Check if the message is forwarded.
        
        Forwarded messages are not allowed for attendance as they could be
        reused from previous submissions.
        """
        # In python-telegram-bot v20+, forward_origin replaces forward_date/from/from_chat
        # Check for forward_origin first (v20+)
        if hasattr(message, 'forward_origin') and message.forward_origin is not None:
            return ValidationResult(
                is_valid=False,
                error_message="Tin nhan chuyen tiep khong duoc phep. Vui long gui vi tri truc tiep.",
                error_code="FORWARDED_MESSAGE",
                details={"forward_origin": str(message.forward_origin)}
            )
        
        # Fallback for older versions (v13.x)
        if hasattr(message, 'forward_date') and message.forward_date is not None:
            return ValidationResult(
                is_valid=False,
                error_message="Tin nhan chuyen tiep khong duoc phep. Vui long gui vi tri truc tiep.",
                error_code="FORWARDED_MESSAGE",
                details={"forward_date": str(message.forward_date)}
            )
        
        if hasattr(message, 'forward_from') and message.forward_from is not None:
            return ValidationResult(
                is_valid=False,
                error_message="Tin nhan chuyen tiep khong duoc phep. Vui long gui vi tri truc tiep.",
                error_code="FORWARDED_FROM_USER",
                details={"forward_from": message.forward_from.id}
            )
        
        if hasattr(message, 'forward_from_chat') and message.forward_from_chat is not None:
            return ValidationResult(
                is_valid=False,
                error_message="Tin nhan chuyen tiep khong duoc phep. Vui long gui vi tri truc tiep.",
                error_code="FORWARDED_FROM_CHAT",
                details={"forward_from_chat": message.forward_from_chat.id}
            )
        
        return ValidationResult(is_valid=True)
    
    @staticmethod
    def check_message_timestamp(message: Message) -> ValidationResult:
        """
        Validate that the message is not too old or in the future.
        
        Uses max_location_age_seconds from config to determine maximum age.
        """
        config = get_config()
        max_age_seconds = config.attendance.max_location_age_seconds
        
        now = datetime.now(timezone.utc)
        message_time = message.date
        
        # Ensure message_time is timezone-aware
        if message_time.tzinfo is None:
            message_time = message_time.replace(tzinfo=timezone.utc)
        
        # Check for future timestamps
        time_diff = (message_time - now).total_seconds()
        if time_diff > 5:  # Allow 5 seconds tolerance for clock drift
            return ValidationResult(
                is_valid=False,
                error_message="Message timestamp is in the future.",
                error_code="FUTURE_TIMESTAMP",
                details={
                    "message_time": str(message_time),
                    "server_time": str(now),
                    "diff_seconds": time_diff
                }
            )
        
        # Check for old messages
        age_seconds = (now - message_time).total_seconds()
        if age_seconds > max_age_seconds:
            return ValidationResult(
                is_valid=False,
                error_message=f"Location is too old. Please share your current location (max {max_age_seconds} seconds).",
                error_code="MESSAGE_TOO_OLD",
                details={
                    "message_age_seconds": age_seconds,
                    "max_age_seconds": max_age_seconds
                }
            )
        
        return ValidationResult(is_valid=True)
    
    @staticmethod
    def check_rate_limit(user_id: int) -> ValidationResult:
        """
        Check and update rate limit for a user.
        
        Limits users to MAX_ATTEMPTS_PER_MINUTE attempts per minute.
        """
        now = datetime.now(timezone.utc)
        one_minute_ago = now.timestamp() - 60
        
        # Clean old entries and get recent attempts
        recent_attempts = [
            ts for ts in AntiCheatService._rate_limit_cache[user_id]
            if ts.timestamp() > one_minute_ago
        ]
        
        if len(recent_attempts) >= AntiCheatService.MAX_ATTEMPTS_PER_MINUTE:
            return ValidationResult(
                is_valid=False,
                error_message="Too many attempts. Please wait a minute before trying again.",
                error_code="RATE_LIMIT_EXCEEDED",
                details={
                    "attempts_in_last_minute": len(recent_attempts),
                    "max_attempts": AntiCheatService.MAX_ATTEMPTS_PER_MINUTE
                }
            )
        
        # Add current attempt and update cache
        recent_attempts.append(now)
        AntiCheatService._rate_limit_cache[user_id] = recent_attempts
        
        return ValidationResult(is_valid=True)
    
    @staticmethod
    def check_live_location(message: Message) -> ValidationResult:
        """
        Check if the message contains a live location.
        
        This is an informational check - live locations are valid but
        we log this for potential future analysis.
        """
        if message.location and message.location.live_period:
            logger.info(
                f"Live location detected from user {message.from_user.id}, "
                f"live_period={message.location.live_period}"
            )
            return ValidationResult(
                is_valid=True,
                details={
                    "is_live_location": True,
                    "live_period": message.location.live_period
                }
            )
        
        return ValidationResult(
            is_valid=True,
            details={"is_live_location": False}
        )
    
    @staticmethod
    def analyze_location_pattern(
        user_id: int,
        lat: float,
        lon: float
    ) -> ValidationResult:
        """
        Analyze location patterns for potential fraud.
        
        Placeholder for future implementation of pattern analysis:
        - Detecting impossible travel speeds
        - Identifying suspicious location clusters
        - Flagging unusual check-in patterns
        """
        # TODO: Implement pattern analysis
        # This could include:
        # - Tracking location history per user
        # - Calculating travel speeds between check-ins
        # - Detecting spoofed/mock locations
        # - Identifying shared device usage
        
        logger.debug(
            f"Location pattern analysis placeholder for user {user_id}: "
            f"lat={lat}, lon={lon}"
        )
        
        return ValidationResult(
            is_valid=True,
            details={
                "pattern_analysis": "not_implemented",
                "user_id": user_id,
                "latitude": lat,
                "longitude": lon
            }
        )
    
    @staticmethod
    def log_validation_attempt(
        user_id: int,
        result: ValidationResult,
        lat: Optional[float] = None,
        lon: Optional[float] = None
    ) -> None:
        """
        Log a validation attempt for audit purposes.
        
        All validation attempts are logged, with additional detail for failures.
        """
        if result.is_valid:
            logger.info(
                f"Validation passed for user {user_id}: "
                f"lat={lat}, lon={lon}"
            )
        else:
            logger.warning(
                f"Validation failed for user {user_id}: "
                f"code={result.error_code}, message={result.error_message}, "
                f"lat={lat}, lon={lon}, details={result.details}"
            )
    
    @staticmethod
    def clear_rate_limit(user_id: int) -> None:
        """
        Clear rate limit for a specific user.
        
        Useful for admin overrides or testing purposes.
        """
        if user_id in AntiCheatService._rate_limit_cache:
            del AntiCheatService._rate_limit_cache[user_id]
            logger.info(f"Rate limit cleared for user {user_id}")
