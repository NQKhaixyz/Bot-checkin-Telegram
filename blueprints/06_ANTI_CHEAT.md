# Anti-Cheat System Implementation Guide

## Overview

This guide covers the implementation of fraud prevention measures to ensure attendance data integrity. The system detects and blocks attempts to fake check-ins using forwarded messages, old location data, or other manipulation techniques.

---

## Prerequisites

- Database models implemented (01_DATABASE_SCHEMA.md)
- Bot core setup completed (02_BOT_CORE.md)
- Geolocation service implemented (05_GEOLOCATION.md)

---

## Fraud Vectors & Countermeasures

### 1. Forwarded Location Messages

**Attack**: User forwards a location message from a previous day when they were at the office.

**Detection**: Check `message.forward_date` attribute. If present, the message was forwarded.

```
Original Message          Forwarded Message
┌─────────────────┐       ┌─────────────────┐
│ Location: X,Y   │       │ Location: X,Y   │
│ date: Today     │  -->  │ date: Today     │
│ forward_date:   │       │ forward_date:   │
│   (none)        │       │   Yesterday     │ <-- DETECTED!
└─────────────────┘       └─────────────────┘
```

### 2. Stale Location Data

**Attack**: User enables airplane mode, captures location at office, then sends it later from home.

**Detection**: Compare `message.date` with server time. If difference exceeds threshold, reject.

```
Timeline:
08:00 - User at office, captures location (but doesn't send)
08:05 - User leaves office
09:30 - User at home, sends captured location
       Server time: 09:30
       Message time: 08:00
       Difference: 90 minutes > 60 seconds threshold
       --> REJECTED!
```

### 3. Location Spoofing Apps

**Attack**: User uses GPS spoofing app to fake their location.

**Mitigation**: 
- Live Location has continuous updates (harder to spoof)
- Cross-reference with IP geolocation (advanced)
- Monitor for suspicious patterns (multiple precise check-ins)

### 4. Desktop/Web Check-ins

**Attack**: User sends location from desktop Telegram (which doesn't have GPS).

**Mitigation**: Desktop clients cannot send accurate GPS location. The `request_location` button only works on mobile.

---

## Implementation Steps

### Step 1: Create Anti-Cheat Service

**File: `src/services/anti_cheat.py`**

```python
"""
Anti-cheat service for detecting fraudulent attendance attempts.

Implements multiple validation layers:
1. Forward detection - Blocks forwarded location messages
2. Timestamp validation - Blocks stale location data
3. Rate limiting - Prevents rapid check-in attempts
4. Pattern analysis - Detects suspicious behavior (optional)
"""

import logging
from datetime import datetime, timedelta
from typing import Optional
from dataclasses import dataclass
from collections import defaultdict

from telegram import Message
import pytz

from src.config import config

logger = logging.getLogger(__name__)


@dataclass
class ValidationResult:
    """Result of anti-cheat validation."""
    is_valid: bool
    error_message: str = ""
    error_code: str = ""
    details: dict = None
    
    def __post_init__(self):
        if self.details is None:
            self.details = {}


class AntiCheatService:
    """
    Service class for fraud detection and prevention.
    
    Validates location messages against multiple criteria to ensure
    authenticity of attendance check-ins.
    """
    
    # Rate limiting storage: user_id -> list of attempt timestamps
    _rate_limit_cache: dict = defaultdict(list)
    
    # Maximum attempts per minute
    MAX_ATTEMPTS_PER_MINUTE = 3
    
    @staticmethod
    def get_timezone():
        """Get configured timezone."""
        return pytz.timezone(config.timezone.timezone)
    
    @staticmethod
    def validate_location_message(message: Message) -> ValidationResult:
        """
        Perform all anti-cheat validations on a location message.
        
        Runs through all validation checks and returns the first failure,
        or success if all checks pass.
        
        Args:
            message: Telegram Message object containing location
            
        Returns:
            ValidationResult with validation status and any error details
            
        Example:
            >>> result = AntiCheatService.validate_location_message(message)
            >>> if not result.is_valid:
            ...     print(f"Rejected: {result.error_message}")
        """
        user_id = message.from_user.id
        
        # Check 1: Forward detection
        forward_result = AntiCheatService.check_forwarded_message(message)
        if not forward_result.is_valid:
            logger.warning(
                f"Anti-cheat: Forwarded message detected from user {user_id}"
            )
            return forward_result
        
        # Check 2: Timestamp validation
        timestamp_result = AntiCheatService.check_message_timestamp(message)
        if not timestamp_result.is_valid:
            logger.warning(
                f"Anti-cheat: Stale location from user {user_id} - "
                f"{timestamp_result.details.get('age_seconds', 0)}s old"
            )
            return timestamp_result
        
        # Check 3: Rate limiting
        rate_result = AntiCheatService.check_rate_limit(user_id)
        if not rate_result.is_valid:
            logger.warning(
                f"Anti-cheat: Rate limit exceeded for user {user_id}"
            )
            return rate_result
        
        # Check 4: Location presence
        if not message.location:
            return ValidationResult(
                is_valid=False,
                error_message="Tin nhan khong chua vi tri.",
                error_code="NO_LOCATION"
            )
        
        # All checks passed
        logger.info(f"Anti-cheat: All validations passed for user {user_id}")
        return ValidationResult(is_valid=True)
    
    @staticmethod
    def check_forwarded_message(message: Message) -> ValidationResult:
        """
        Check if the message is a forwarded message.
        
        Forwarded messages have a forward_date attribute set.
        
        Args:
            message: Telegram Message object
            
        Returns:
            ValidationResult - invalid if message is forwarded
        """
        # Check forward_date (present if forwarded from another chat)
        if message.forward_date is not None:
            return ValidationResult(
                is_valid=False,
                error_message=(
                    "Khong the su dung vi tri duoc chuyen tiep!\n"
                    "Vui long gui vi tri hien tai truc tiep."
                ),
                error_code="FORWARDED_MESSAGE",
                details={
                    "forward_date": message.forward_date.isoformat()
                }
            )
        
        # Check forward_from (present if forwarded from a user)
        if message.forward_from is not None:
            return ValidationResult(
                is_valid=False,
                error_message=(
                    "Khong the su dung vi tri duoc chuyen tiep!\n"
                    "Vui long gui vi tri hien tai truc tiep."
                ),
                error_code="FORWARDED_FROM_USER",
                details={
                    "forward_from": message.forward_from.id
                }
            )
        
        # Check forward_from_chat (present if forwarded from a channel/group)
        if message.forward_from_chat is not None:
            return ValidationResult(
                is_valid=False,
                error_message=(
                    "Khong the su dung vi tri duoc chuyen tiep!\n"
                    "Vui long gui vi tri hien tai truc tiep."
                ),
                error_code="FORWARDED_FROM_CHAT",
                details={
                    "forward_from_chat": message.forward_from_chat.id
                }
            )
        
        return ValidationResult(is_valid=True)
    
    @staticmethod
    def check_message_timestamp(message: Message) -> ValidationResult:
        """
        Validate that the message timestamp is recent.
        
        Compares the message date with the current server time.
        Messages older than the configured threshold are rejected.
        
        Args:
            message: Telegram Message object
            
        Returns:
            ValidationResult - invalid if message is too old
        """
        tz = AntiCheatService.get_timezone()
        server_time = datetime.now(tz)
        
        # Get message time (Telegram times are in UTC)
        message_time = message.date
        if message_time.tzinfo is None:
            message_time = pytz.UTC.localize(message_time)
        
        # Convert to local timezone for comparison
        message_time_local = message_time.astimezone(tz)
        
        # Calculate age in seconds
        age = (server_time - message_time_local).total_seconds()
        
        # Get threshold from config
        max_age = config.attendance.max_location_age_seconds
        
        if age > max_age:
            return ValidationResult(
                is_valid=False,
                error_message=(
                    f"Vi tri da qua cu ({int(age)} giay truoc)!\n"
                    f"Vui long gui vi tri moi (toi da {max_age} giay)."
                ),
                error_code="STALE_LOCATION",
                details={
                    "age_seconds": age,
                    "max_age_seconds": max_age,
                    "message_time": message_time_local.isoformat(),
                    "server_time": server_time.isoformat()
                }
            )
        
        # Also check for future timestamps (clock manipulation)
        if age < -30:  # Allow 30 seconds for clock sync issues
            return ValidationResult(
                is_valid=False,
                error_message=(
                    "Thoi gian tin nhan khong hop le.\n"
                    "Vui long kiem tra dong ho thiet bi."
                ),
                error_code="FUTURE_TIMESTAMP",
                details={
                    "age_seconds": age,
                    "message_time": message_time_local.isoformat(),
                    "server_time": server_time.isoformat()
                }
            )
        
        return ValidationResult(is_valid=True)
    
    @staticmethod
    def check_rate_limit(user_id: int) -> ValidationResult:
        """
        Check if user has exceeded rate limit for check-in attempts.
        
        Prevents rapid repeated attempts which might indicate automation
        or brute-force location spoofing.
        
        Args:
            user_id: Telegram user ID
            
        Returns:
            ValidationResult - invalid if rate limit exceeded
        """
        now = datetime.now()
        cache = AntiCheatService._rate_limit_cache
        
        # Clean old entries (older than 1 minute)
        cutoff = now - timedelta(minutes=1)
        cache[user_id] = [
            ts for ts in cache[user_id] 
            if ts > cutoff
        ]
        
        # Check count
        if len(cache[user_id]) >= AntiCheatService.MAX_ATTEMPTS_PER_MINUTE:
            return ValidationResult(
                is_valid=False,
                error_message=(
                    "Ban dang gui vi tri qua nhanh.\n"
                    "Vui long doi 1 phut truoc khi thu lai."
                ),
                error_code="RATE_LIMITED",
                details={
                    "attempts": len(cache[user_id]),
                    "limit": AntiCheatService.MAX_ATTEMPTS_PER_MINUTE
                }
            )
        
        # Record this attempt
        cache[user_id].append(now)
        
        return ValidationResult(is_valid=True)
    
    @staticmethod
    def check_live_location(message: Message) -> ValidationResult:
        """
        Check if the location is a live location share.
        
        Live locations are more trustworthy as they update continuously
        and are harder to spoof.
        
        Args:
            message: Telegram Message object
            
        Returns:
            ValidationResult with live location status (informational)
            
        Note:
            This is an informational check. The bot accepts both live
            and static locations, but live locations provide higher confidence.
        """
        location = message.location
        
        if location and location.live_period:
            return ValidationResult(
                is_valid=True,
                details={
                    "is_live": True,
                    "live_period": location.live_period
                }
            )
        
        return ValidationResult(
            is_valid=True,
            details={
                "is_live": False
            }
        )
    
    @staticmethod
    def analyze_location_pattern(
        user_id: int,
        latitude: float,
        longitude: float
    ) -> ValidationResult:
        """
        Analyze location patterns for suspicious behavior.
        
        Detects anomalies like:
        - Same exact coordinates repeatedly (GPS spoofing)
        - Impossible travel speeds between check-ins
        - Check-ins from unusual locations
        
        Args:
            user_id: Telegram user ID
            latitude: Current latitude
            longitude: Current longitude
            
        Returns:
            ValidationResult with pattern analysis
            
        Note:
            This is an advanced feature. Basic implementation logs
            suspicious patterns but doesn't block.
        """
        # TODO: Implement pattern analysis
        # This would require:
        # 1. Storing recent check-in coordinates
        # 2. Comparing with current coordinates
        # 3. Calculating travel speed between points
        # 4. Flagging impossible scenarios
        
        # For now, just pass
        return ValidationResult(is_valid=True)
    
    @staticmethod
    def log_validation_attempt(
        user_id: int,
        result: ValidationResult,
        latitude: float = None,
        longitude: float = None
    ) -> None:
        """
        Log validation attempt for audit purposes.
        
        Args:
            user_id: Telegram user ID
            result: Validation result
            latitude: User's latitude (if available)
            longitude: User's longitude (if available)
        """
        if result.is_valid:
            logger.info(
                f"Validation passed: user={user_id}, "
                f"coords=({latitude}, {longitude})"
            )
        else:
            logger.warning(
                f"Validation failed: user={user_id}, "
                f"code={result.error_code}, "
                f"coords=({latitude}, {longitude}), "
                f"details={result.details}"
            )
    
    @staticmethod
    def clear_rate_limit(user_id: int) -> None:
        """
        Clear rate limit for a user (admin function).
        
        Args:
            user_id: Telegram user ID
        """
        if user_id in AntiCheatService._rate_limit_cache:
            del AntiCheatService._rate_limit_cache[user_id]
            logger.info(f"Rate limit cleared for user {user_id}")
```

### Step 2: Create Enhanced Validation Messages

**Add to `src/constants.py`:**

```python
# Add these to the Messages class

class Messages:
    # ... existing messages ...
    
    # Anti-cheat messages
    LOCATION_FORWARDED = (
        "Khong the su dung vi tri duoc chuyen tiep!\n"
        "Vui long gui vi tri hien tai truc tiep tu thiet bi cua ban."
    )
    
    LOCATION_TOO_OLD = (
        "Vi tri da qua cu ({age} giay truoc)!\n"
        "Vui long gui vi tri moi.\n"
        "Luu y: Vi tri chi hop le trong vong {max_age} giay."
    )
    
    LOCATION_FUTURE = (
        "Thoi gian tin nhan khong hop le.\n"
        "Vui long kiem tra dong ho tren thiet bi cua ban."
    )
    
    RATE_LIMITED = (
        "Ban dang gui vi tri qua nhanh.\n"
        "Vui long doi {wait_seconds} giay truoc khi thu lai."
    )
    
    SUSPICIOUS_PATTERN = (
        "Phat hien hoat dong bat thuong.\n"
        "Vui long lien he Admin neu ban cho rang day la loi."
    )
```

### Step 3: Create Anti-Cheat Database Table (Optional)

For auditing purposes, you may want to log all validation failures:

**Add to `src/database/models.py`:**

```python
class ValidationLog(Base):
    """
    Log of anti-cheat validation attempts.
    
    Stores all validation failures for audit and analysis.
    """
    __tablename__ = "validation_logs"
    
    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        autoincrement=True
    )
    
    user_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("users.user_id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    
    error_code: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        index=True
    )
    
    error_message: Mapped[str] = mapped_column(
        String(500),
        nullable=False
    )
    
    details: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="JSON string of validation details"
    )
    
    user_latitude: Mapped[Optional[float]] = mapped_column(
        Float,
        nullable=True
    )
    
    user_longitude: Mapped[Optional[float]] = mapped_column(
        Float,
        nullable=True
    )
    
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        nullable=False,
        index=True
    )
    
    # Relationship
    user: Mapped["User"] = relationship("User")
```

### Step 4: Integrate with Check-in Handler

**Update `src/bot/handlers/checkin.py`:**

```python
async def location_handler(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
) -> None:
    """Handle location messages with anti-cheat validation."""
    user_id = update.effective_user.id
    message = update.message
    
    # ... existing user validation ...
    
    # =================================================================
    # ANTI-CHEAT VALIDATION (CRITICAL)
    # =================================================================
    
    validation = AntiCheatService.validate_location_message(message)
    
    # Log the attempt
    AntiCheatService.log_validation_attempt(
        user_id=user_id,
        result=validation,
        latitude=message.location.latitude if message.location else None,
        longitude=message.location.longitude if message.location else None
    )
    
    if not validation.is_valid:
        await message.reply_text(
            validation.error_message,
            reply_markup=Keyboards.main_menu()
        )
        
        # Optional: Store in database for audit
        # await store_validation_failure(user_id, validation)
        
        return
    
    # ... continue with location verification and check-in ...
```

---

## Testing Anti-Cheat System

```python
"""Test file: tests/test_anti_cheat.py"""

import pytest
from datetime import datetime, timedelta
from unittest.mock import Mock, MagicMock
import pytz

from src.services.anti_cheat import AntiCheatService, ValidationResult


def create_mock_message(
    forward_date=None,
    forward_from=None,
    message_date=None,
    has_location=True
):
    """Create a mock Telegram message for testing."""
    message = Mock()
    message.forward_date = forward_date
    message.forward_from = forward_from
    message.forward_from_chat = None
    message.from_user = Mock()
    message.from_user.id = 12345
    
    if message_date:
        message.date = message_date
    else:
        message.date = datetime.now(pytz.UTC)
    
    if has_location:
        message.location = Mock()
        message.location.latitude = 21.0285
        message.location.longitude = 105.8542
        message.location.live_period = None
    else:
        message.location = None
    
    return message


class TestForwardDetection:
    """Tests for forwarded message detection."""
    
    def test_normal_message_passes(self):
        """Normal (non-forwarded) message should pass."""
        message = create_mock_message()
        result = AntiCheatService.check_forwarded_message(message)
        assert result.is_valid == True
    
    def test_forwarded_message_blocked(self):
        """Forwarded message should be blocked."""
        message = create_mock_message(
            forward_date=datetime.now(pytz.UTC)
        )
        result = AntiCheatService.check_forwarded_message(message)
        assert result.is_valid == False
        assert result.error_code == "FORWARDED_MESSAGE"
    
    def test_forwarded_from_user_blocked(self):
        """Message forwarded from user should be blocked."""
        message = create_mock_message()
        message.forward_from = Mock()
        message.forward_from.id = 99999
        
        result = AntiCheatService.check_forwarded_message(message)
        assert result.is_valid == False
        assert result.error_code == "FORWARDED_FROM_USER"


class TestTimestampValidation:
    """Tests for message timestamp validation."""
    
    def test_recent_message_passes(self):
        """Recent message (within threshold) should pass."""
        message = create_mock_message(
            message_date=datetime.now(pytz.UTC)
        )
        result = AntiCheatService.check_message_timestamp(message)
        assert result.is_valid == True
    
    def test_old_message_blocked(self):
        """Old message (exceeds threshold) should be blocked."""
        old_time = datetime.now(pytz.UTC) - timedelta(minutes=5)
        message = create_mock_message(message_date=old_time)
        
        result = AntiCheatService.check_message_timestamp(message)
        assert result.is_valid == False
        assert result.error_code == "STALE_LOCATION"
    
    def test_future_message_blocked(self):
        """Future timestamp should be blocked."""
        future_time = datetime.now(pytz.UTC) + timedelta(minutes=5)
        message = create_mock_message(message_date=future_time)
        
        result = AntiCheatService.check_message_timestamp(message)
        assert result.is_valid == False
        assert result.error_code == "FUTURE_TIMESTAMP"


class TestRateLimiting:
    """Tests for rate limiting."""
    
    def setup_method(self):
        """Clear rate limit cache before each test."""
        AntiCheatService._rate_limit_cache.clear()
    
    def test_first_attempt_passes(self):
        """First attempt should pass."""
        result = AntiCheatService.check_rate_limit(12345)
        assert result.is_valid == True
    
    def test_rate_limit_exceeded(self):
        """Exceeding rate limit should be blocked."""
        user_id = 12345
        
        # Make MAX_ATTEMPTS_PER_MINUTE attempts
        for _ in range(AntiCheatService.MAX_ATTEMPTS_PER_MINUTE):
            AntiCheatService.check_rate_limit(user_id)
        
        # Next attempt should fail
        result = AntiCheatService.check_rate_limit(user_id)
        assert result.is_valid == False
        assert result.error_code == "RATE_LIMITED"
    
    def test_clear_rate_limit(self):
        """Clearing rate limit should allow new attempts."""
        user_id = 12345
        
        # Exceed rate limit
        for _ in range(AntiCheatService.MAX_ATTEMPTS_PER_MINUTE + 1):
            AntiCheatService.check_rate_limit(user_id)
        
        # Clear and retry
        AntiCheatService.clear_rate_limit(user_id)
        result = AntiCheatService.check_rate_limit(user_id)
        assert result.is_valid == True


class TestFullValidation:
    """Tests for complete validation flow."""
    
    def setup_method(self):
        """Reset state before each test."""
        AntiCheatService._rate_limit_cache.clear()
    
    def test_valid_message_passes_all_checks(self):
        """Valid message should pass all checks."""
        message = create_mock_message()
        result = AntiCheatService.validate_location_message(message)
        assert result.is_valid == True
    
    def test_no_location_fails(self):
        """Message without location should fail."""
        message = create_mock_message(has_location=False)
        result = AntiCheatService.validate_location_message(message)
        assert result.is_valid == False
        assert result.error_code == "NO_LOCATION"
```

---

## Security Best Practices

### 1. Defense in Depth

Don't rely on a single validation. Use multiple layers:

```python
def validate_checkin(message, user_id):
    # Layer 1: Message validation
    if not validate_message(message):
        return False
    
    # Layer 2: Timestamp validation
    if not validate_timestamp(message):
        return False
    
    # Layer 3: Rate limiting
    if not check_rate_limit(user_id):
        return False
    
    # Layer 4: Geofence validation
    if not validate_geofence(message.location):
        return False
    
    return True
```

### 2. Fail Securely

When validation fails, provide generic messages that don't reveal detection methods:

```python
# Bad - reveals detection method
"Forwarded messages are not allowed"

# Better - generic message
"Location verification failed. Please send your current location directly."
```

### 3. Audit Everything

Log all validation attempts for later analysis:

```python
logger.info(
    f"Validation attempt: user={user_id}, "
    f"success={result.is_valid}, "
    f"code={result.error_code}, "
    f"ip={client_ip}"  # If available
)
```

### 4. Admin Alerts

Notify admins of suspicious patterns:

```python
if failed_attempts_today > 5:
    await notify_admins(
        f"User {user_id} has {failed_attempts_today} failed attempts today"
    )
```

---

## Verification Checklist

Before proceeding to the next blueprint, verify:

- [ ] `src/services/anti_cheat.py` created with all validations
- [ ] Forward detection blocks forwarded messages
- [ ] Timestamp validation blocks old messages
- [ ] Rate limiting prevents rapid attempts
- [ ] Integration with check-in handler works
- [ ] Validation failures are logged
- [ ] Error messages are user-friendly
- [ ] Tests cover all validation scenarios

---

## Next Steps

Proceed to `07_REPORTING.md` to implement the reporting and export system.
