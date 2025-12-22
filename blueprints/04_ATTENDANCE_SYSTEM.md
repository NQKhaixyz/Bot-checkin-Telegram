# Attendance System Implementation Guide

## Overview

This guide covers the core attendance tracking functionality including check-in, check-out, attendance service, late detection, and daily attendance management.

---

## Prerequisites

- Database models implemented (01_DATABASE_SCHEMA.md)
- Bot core setup completed (02_BOT_CORE.md)
- User management implemented (03_USER_MANAGEMENT.md)

---

## Attendance Flow

```
┌──────────────────────────────────────────────────────────────┐
│                      CHECK-IN FLOW                           │
├──────────────────────────────────────────────────────────────┤
│                                                              │
│  User clicks "Check-in"                                      │
│         │                                                    │
│         ▼                                                    │
│  ┌─────────────────┐                                         │
│  │ Check if active │──No──▶ "Account not approved"           │
│  └────────┬────────┘                                         │
│           │ Yes                                              │
│           ▼                                                  │
│  ┌─────────────────┐                                         │
│  │ Already checked │──Yes──▶ "Already checked in at HH:MM"   │
│  │ in today?       │                                         │
│  └────────┬────────┘                                         │
│           │ No                                               │
│           ▼                                                  │
│  ┌─────────────────┐                                         │
│  │ Request GPS     │                                         │
│  │ Location        │                                         │
│  └────────┬────────┘                                         │
│           │                                                  │
│           ▼                                                  │
│  ┌─────────────────┐                                         │
│  │ Validate        │──Fail──▶ See 06_ANTI_CHEAT.md           │
│  │ Location        │                                         │
│  └────────┬────────┘                                         │
│           │ Pass                                             │
│           ▼                                                  │
│  ┌─────────────────┐                                         │
│  │ Calculate       │                                         │
│  │ Distance        │                                         │
│  └────────┬────────┘                                         │
│           │                                                  │
│      ┌────┴────┐                                             │
│      │         │                                             │
│  d <= R     d > R                                            │
│      │         │                                             │
│      ▼         ▼                                             │
│  SUCCESS    FAIL: "You are XXm away"                         │
│      │                                                       │
│      ▼                                                       │
│  ┌─────────────────┐                                         │
│  │ Check if late   │                                         │
│  └────────┬────────┘                                         │
│           │                                                  │
│           ▼                                                  │
│  ┌─────────────────┐                                         │
│  │ Save to DB      │                                         │
│  └────────┬────────┘                                         │
│           │                                                  │
│           ▼                                                  │
│  "Check-in successful at HH:MM"                              │
│                                                              │
└──────────────────────────────────────────────────────────────┘
```

---

## Implementation Steps

### Step 1: Create Attendance Service

**File: `src/services/attendance.py`**

```python
"""
Attendance management service.

Handles all attendance-related business logic including check-in,
check-out, late detection, and attendance queries.
"""

import logging
from datetime import datetime, date, time, timedelta
from typing import Optional, List, Tuple
from dataclasses import dataclass

from sqlalchemy import func, and_
from sqlalchemy.orm import Session
import pytz

from src.database import (
    AttendanceLog, AttendanceType, User, Location,
    get_db_session
)
from src.config import config

logger = logging.getLogger(__name__)


@dataclass
class CheckInResult:
    """Result of a check-in attempt."""
    success: bool
    message: str
    attendance_log: Optional[AttendanceLog] = None
    is_late: bool = False
    late_minutes: int = 0
    distance: float = 0.0


@dataclass
class CheckOutResult:
    """Result of a check-out attempt."""
    success: bool
    message: str
    attendance_log: Optional[AttendanceLog] = None
    work_duration: Optional[timedelta] = None


@dataclass
class DailyAttendance:
    """Daily attendance summary for a user."""
    user_id: int
    user_name: str
    date: date
    check_in_time: Optional[datetime] = None
    check_out_time: Optional[datetime] = None
    is_late: bool = False
    late_minutes: int = 0
    work_duration: Optional[timedelta] = None
    status: str = "absent"  # present, late, absent


class AttendanceService:
    """Service class for attendance operations."""
    
    @staticmethod
    def get_timezone():
        """Get configured timezone."""
        return pytz.timezone(config.timezone.timezone)
    
    @staticmethod
    def get_current_time() -> datetime:
        """Get current time in configured timezone."""
        tz = AttendanceService.get_timezone()
        return datetime.now(tz)
    
    @staticmethod
    def is_late(check_time: datetime) -> Tuple[bool, int]:
        """
        Check if a check-in time is considered late.
        
        Args:
            check_time: The check-in datetime
            
        Returns:
            Tuple of (is_late, minutes_late)
        """
        tz = AttendanceService.get_timezone()
        
        # Ensure check_time is timezone aware
        if check_time.tzinfo is None:
            check_time = tz.localize(check_time)
        
        # Get work start time for the check-in date
        work_start = datetime.combine(
            check_time.date(),
            config.attendance.work_start_time
        )
        work_start = tz.localize(work_start)
        
        # Add threshold
        late_threshold = work_start + timedelta(
            minutes=config.attendance.late_threshold_minutes
        )
        
        if check_time > late_threshold:
            minutes_late = int((check_time - work_start).total_seconds() / 60)
            return True, minutes_late
        
        return False, 0
    
    @staticmethod
    def has_checked_in_today(user_id: int, target_date: date = None) -> bool:
        """
        Check if user has already checked in on a specific date.
        
        Args:
            user_id: Telegram user ID
            target_date: Date to check (defaults to today)
            
        Returns:
            True if user has checked in
        """
        if target_date is None:
            target_date = AttendanceService.get_current_time().date()
        
        with get_db_session() as db:
            exists = db.query(AttendanceLog).filter(
                AttendanceLog.user_id == user_id,
                AttendanceLog.type == AttendanceType.IN,
                func.date(AttendanceLog.timestamp) == target_date
            ).first() is not None
            
            return exists
    
    @staticmethod
    def has_checked_out_today(user_id: int, target_date: date = None) -> bool:
        """
        Check if user has already checked out on a specific date.
        
        Args:
            user_id: Telegram user ID
            target_date: Date to check (defaults to today)
            
        Returns:
            True if user has checked out
        """
        if target_date is None:
            target_date = AttendanceService.get_current_time().date()
        
        with get_db_session() as db:
            exists = db.query(AttendanceLog).filter(
                AttendanceLog.user_id == user_id,
                AttendanceLog.type == AttendanceType.OUT,
                func.date(AttendanceLog.timestamp) == target_date
            ).first() is not None
            
            return exists
    
    @staticmethod
    def get_today_checkin(user_id: int) -> Optional[AttendanceLog]:
        """
        Get user's check-in record for today.
        
        Args:
            user_id: Telegram user ID
            
        Returns:
            AttendanceLog or None
        """
        today = AttendanceService.get_current_time().date()
        
        with get_db_session() as db:
            log = db.query(AttendanceLog).filter(
                AttendanceLog.user_id == user_id,
                AttendanceLog.type == AttendanceType.IN,
                func.date(AttendanceLog.timestamp) == today
            ).first()
            
            if log:
                db.expunge(log)
            return log
    
    @staticmethod
    def record_checkin(
        user_id: int,
        location_id: int,
        user_latitude: float,
        user_longitude: float,
        distance: float
    ) -> CheckInResult:
        """
        Record a check-in for a user.
        
        Args:
            user_id: Telegram user ID
            location_id: Office location ID
            user_latitude: User's GPS latitude
            user_longitude: User's GPS longitude
            distance: Calculated distance from office
            
        Returns:
            CheckInResult with success status and details
        """
        current_time = AttendanceService.get_current_time()
        
        # Check if already checked in
        if AttendanceService.has_checked_in_today(user_id):
            existing = AttendanceService.get_today_checkin(user_id)
            return CheckInResult(
                success=False,
                message=f"Da check-in luc {existing.timestamp.strftime('%H:%M')}",
                attendance_log=existing
            )
        
        # Check if late
        is_late, late_minutes = AttendanceService.is_late(current_time)
        
        # Create attendance log
        with get_db_session() as db:
            log = AttendanceLog(
                user_id=user_id,
                location_id=location_id,
                type=AttendanceType.IN,
                timestamp=current_time,
                user_latitude=user_latitude,
                user_longitude=user_longitude,
                distance=distance,
                is_late=is_late
            )
            db.add(log)
            db.flush()
            db.expunge(log)
            
            logger.info(
                f"Check-in recorded: user={user_id}, "
                f"location={location_id}, distance={distance}m, "
                f"late={is_late}"
            )
            
            return CheckInResult(
                success=True,
                message="Check-in thanh cong",
                attendance_log=log,
                is_late=is_late,
                late_minutes=late_minutes,
                distance=distance
            )
    
    @staticmethod
    def record_checkout(
        user_id: int,
        location_id: Optional[int],
        user_latitude: float,
        user_longitude: float,
        distance: float
    ) -> CheckOutResult:
        """
        Record a check-out for a user.
        
        Args:
            user_id: Telegram user ID
            location_id: Office location ID (optional for checkout)
            user_latitude: User's GPS latitude
            user_longitude: User's GPS longitude
            distance: Calculated distance from office
            
        Returns:
            CheckOutResult with success status and work duration
        """
        current_time = AttendanceService.get_current_time()
        
        # Check if checked in today
        checkin = AttendanceService.get_today_checkin(user_id)
        if not checkin:
            return CheckOutResult(
                success=False,
                message="Ban chua check-in hom nay"
            )
        
        # Check if already checked out
        if AttendanceService.has_checked_out_today(user_id):
            return CheckOutResult(
                success=False,
                message="Ban da check-out hom nay roi"
            )
        
        # Calculate work duration
        work_duration = current_time - checkin.timestamp.replace(
            tzinfo=AttendanceService.get_timezone()
        )
        
        # Create checkout log
        with get_db_session() as db:
            log = AttendanceLog(
                user_id=user_id,
                location_id=location_id,
                type=AttendanceType.OUT,
                timestamp=current_time,
                user_latitude=user_latitude,
                user_longitude=user_longitude,
                distance=distance,
                is_late=False  # Late only applies to check-in
            )
            db.add(log)
            db.flush()
            db.expunge(log)
            
            logger.info(
                f"Check-out recorded: user={user_id}, "
                f"work_duration={work_duration}"
            )
            
            return CheckOutResult(
                success=True,
                message="Check-out thanh cong",
                attendance_log=log,
                work_duration=work_duration
            )
    
    @staticmethod
    def get_user_attendance_today(user_id: int) -> DailyAttendance:
        """
        Get user's attendance summary for today.
        
        Args:
            user_id: Telegram user ID
            
        Returns:
            DailyAttendance summary object
        """
        today = AttendanceService.get_current_time().date()
        
        with get_db_session() as db:
            user = db.query(User).filter(User.user_id == user_id).first()
            if not user:
                return None
            
            logs = db.query(AttendanceLog).filter(
                AttendanceLog.user_id == user_id,
                func.date(AttendanceLog.timestamp) == today
            ).all()
            
            checkin = next(
                (l for l in logs if l.type == AttendanceType.IN), 
                None
            )
            checkout = next(
                (l for l in logs if l.type == AttendanceType.OUT), 
                None
            )
            
            # Determine status
            if checkin:
                status = "late" if checkin.is_late else "present"
            else:
                status = "absent"
            
            # Calculate work duration
            work_duration = None
            if checkin and checkout:
                work_duration = checkout.timestamp - checkin.timestamp
            
            # Calculate late minutes
            late_minutes = 0
            if checkin and checkin.is_late:
                _, late_minutes = AttendanceService.is_late(checkin.timestamp)
            
            return DailyAttendance(
                user_id=user_id,
                user_name=user.full_name,
                date=today,
                check_in_time=checkin.timestamp if checkin else None,
                check_out_time=checkout.timestamp if checkout else None,
                is_late=checkin.is_late if checkin else False,
                late_minutes=late_minutes,
                work_duration=work_duration,
                status=status
            )
    
    @staticmethod
    def get_all_attendance_today() -> List[DailyAttendance]:
        """
        Get attendance summary for all active users today.
        
        Returns:
            List of DailyAttendance for all users
        """
        from src.services.user_service import UserService
        
        active_users = UserService.get_active_users()
        results = []
        
        for user in active_users:
            attendance = AttendanceService.get_user_attendance_today(user.user_id)
            if attendance:
                results.append(attendance)
        
        return results
    
    @staticmethod
    def get_user_attendance_history(
        user_id: int,
        start_date: date,
        end_date: date
    ) -> List[AttendanceLog]:
        """
        Get user's attendance logs for a date range.
        
        Args:
            user_id: Telegram user ID
            start_date: Start of date range
            end_date: End of date range
            
        Returns:
            List of AttendanceLog objects
        """
        with get_db_session() as db:
            logs = db.query(AttendanceLog).filter(
                AttendanceLog.user_id == user_id,
                func.date(AttendanceLog.timestamp) >= start_date,
                func.date(AttendanceLog.timestamp) <= end_date
            ).order_by(AttendanceLog.timestamp).all()
            
            for log in logs:
                db.expunge(log)
            
            return logs
    
    @staticmethod
    def get_monthly_summary(
        user_id: int,
        year: int,
        month: int
    ) -> dict:
        """
        Get monthly attendance summary for a user.
        
        Args:
            user_id: Telegram user ID
            year: Year
            month: Month (1-12)
            
        Returns:
            Dictionary with monthly statistics
        """
        from calendar import monthrange
        
        _, days_in_month = monthrange(year, month)
        start_date = date(year, month, 1)
        end_date = date(year, month, days_in_month)
        
        with get_db_session() as db:
            # Count check-ins
            checkins = db.query(AttendanceLog).filter(
                AttendanceLog.user_id == user_id,
                AttendanceLog.type == AttendanceType.IN,
                func.date(AttendanceLog.timestamp) >= start_date,
                func.date(AttendanceLog.timestamp) <= end_date
            ).all()
            
            total_days = len(checkins)
            late_days = sum(1 for c in checkins if c.is_late)
            on_time_days = total_days - late_days
            
            # Calculate total late minutes
            total_late_minutes = 0
            for checkin in checkins:
                if checkin.is_late:
                    _, minutes = AttendanceService.is_late(checkin.timestamp)
                    total_late_minutes += minutes
            
            return {
                "year": year,
                "month": month,
                "total_days": total_days,
                "on_time_days": on_time_days,
                "late_days": late_days,
                "total_late_minutes": total_late_minutes,
                "attendance_rate": (total_days / days_in_month) * 100 if days_in_month > 0 else 0
            }
    
    @staticmethod
    def format_duration(duration: timedelta) -> str:
        """
        Format a timedelta as a human-readable string.
        
        Args:
            duration: timedelta object
            
        Returns:
            Formatted string like "8h 30m"
        """
        total_seconds = int(duration.total_seconds())
        hours = total_seconds // 3600
        minutes = (total_seconds % 3600) // 60
        
        if hours > 0:
            return f"{hours}h {minutes}m"
        return f"{minutes}m"
```

### Step 2: Create Check-in/Check-out Handlers

**File: `src/bot/handlers/checkin.py`**

```python
"""
Check-in and check-out command handlers.

Handles the attendance recording flow including location requests
and validation.
"""

import logging
from datetime import datetime

from telegram import Update, Message
from telegram.ext import ContextTypes

from src.services.attendance import AttendanceService
from src.services.user_service import UserService
from src.services.geolocation import GeolocationService
from src.services.anti_cheat import AntiCheatService
from src.database import User, Location
from src.constants import Messages, KeyboardLabels
from src.bot.keyboards import Keyboards
from src.bot.middlewares import require_active, log_action
from src.config import config

logger = logging.getLogger(__name__)

# Store pending check-in/check-out state per user
# Key: user_id, Value: "checkin" or "checkout"
pending_actions = {}


@require_active
@log_action("request_checkin")
async def checkin_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    user: User = None
) -> None:
    """
    Handle /checkin command or "Check-in" button.
    
    Initiates the check-in flow by requesting user's location.
    """
    user_id = update.effective_user.id
    
    # Check if already checked in today
    if AttendanceService.has_checked_in_today(user_id):
        existing = AttendanceService.get_today_checkin(user_id)
        await update.message.reply_text(
            Messages.CHECKIN_FAILED_ALREADY.format(
                time=existing.timestamp.strftime("%H:%M")
            )
        )
        return
    
    # Check if any locations are configured
    locations = GeolocationService.get_active_locations()
    if not locations:
        await update.message.reply_text(Messages.NO_LOCATION_CONFIGURED)
        return
    
    # Store pending action
    pending_actions[user_id] = "checkin"
    
    # Request location
    await update.message.reply_text(
        Messages.REQUEST_LOCATION,
        reply_markup=Keyboards.request_location()
    )


@require_active
@log_action("request_checkout")
async def checkout_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    user: User = None
) -> None:
    """
    Handle /checkout command or "Check-out" button.
    
    Initiates the check-out flow by requesting user's location.
    """
    user_id = update.effective_user.id
    
    # Check if checked in today
    if not AttendanceService.has_checked_in_today(user_id):
        await update.message.reply_text(Messages.CHECKOUT_FAILED_NO_CHECKIN)
        return
    
    # Check if already checked out today
    if AttendanceService.has_checked_out_today(user_id):
        await update.message.reply_text(
            "Ban da check-out hom nay roi!"
        )
        return
    
    # Store pending action
    pending_actions[user_id] = "checkout"
    
    # Request location
    await update.message.reply_text(
        "Vui long gui vi tri de check-out:",
        reply_markup=Keyboards.request_location()
    )


async def location_handler(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
) -> None:
    """
    Handle location messages from users.
    
    Processes the location for check-in or check-out based on
    the pending action state.
    """
    user_id = update.effective_user.id
    message = update.message
    location = message.location
    
    # Check if user is active
    user = UserService.get_user(user_id)
    if not user or not user.is_active:
        await message.reply_text(Messages.ERROR_NOT_APPROVED)
        return
    
    # Check pending action
    action = pending_actions.get(user_id)
    if not action:
        # No pending action, might be unsolicited location
        await message.reply_text(
            "Vui long su dung nut Check-in hoac Check-out truoc khi gui vi tri.",
            reply_markup=Keyboards.main_menu()
        )
        return
    
    # Clear pending action
    del pending_actions[user_id]
    
    # =================================================================
    # ANTI-CHEAT VALIDATION
    # =================================================================
    
    # Check for forwarded message
    validation = AntiCheatService.validate_location_message(message)
    if not validation.is_valid:
        await message.reply_text(
            validation.error_message,
            reply_markup=Keyboards.main_menu()
        )
        logger.warning(
            f"Anti-cheat failed for user {user_id}: {validation.error_message}"
        )
        return
    
    # =================================================================
    # LOCATION VERIFICATION
    # =================================================================
    
    user_lat = location.latitude
    user_lon = location.longitude
    
    # Find nearest office location
    nearest = GeolocationService.find_nearest_location(user_lat, user_lon)
    
    if not nearest:
        await message.reply_text(
            Messages.NO_LOCATION_CONFIGURED,
            reply_markup=Keyboards.main_menu()
        )
        return
    
    office_location, distance = nearest
    
    # Check if within radius
    if distance > office_location.radius:
        await message.reply_text(
            Messages.CHECKIN_FAILED_DISTANCE.format(
                distance=round(distance),
                radius=office_location.radius
            ),
            reply_markup=Keyboards.main_menu()
        )
        return
    
    # =================================================================
    # PROCESS CHECK-IN OR CHECK-OUT
    # =================================================================
    
    if action == "checkin":
        await process_checkin(
            message, user_id, office_location, 
            user_lat, user_lon, distance
        )
    elif action == "checkout":
        await process_checkout(
            message, user_id, office_location,
            user_lat, user_lon, distance
        )


async def process_checkin(
    message: Message,
    user_id: int,
    location: Location,
    user_lat: float,
    user_lon: float,
    distance: float
) -> None:
    """
    Process a check-in after location validation.
    
    Args:
        message: Telegram message object
        user_id: User's Telegram ID
        location: Office location object
        user_lat: User's latitude
        user_lon: User's longitude
        distance: Distance from office in meters
    """
    result = AttendanceService.record_checkin(
        user_id=user_id,
        location_id=location.id,
        user_latitude=user_lat,
        user_longitude=user_lon,
        distance=distance
    )
    
    if result.success:
        if result.is_late:
            response = Messages.CHECKIN_SUCCESS_LATE.format(
                time=result.attendance_log.timestamp.strftime("%H:%M"),
                location=location.name,
                distance=round(distance),
                late_minutes=result.late_minutes
            )
        else:
            response = Messages.CHECKIN_SUCCESS.format(
                time=result.attendance_log.timestamp.strftime("%H:%M"),
                location=location.name,
                distance=round(distance)
            )
    else:
        response = result.message
    
    await message.reply_text(
        response,
        reply_markup=Keyboards.main_menu()
    )


async def process_checkout(
    message: Message,
    user_id: int,
    location: Location,
    user_lat: float,
    user_lon: float,
    distance: float
) -> None:
    """
    Process a check-out after location validation.
    
    Args:
        message: Telegram message object
        user_id: User's Telegram ID
        location: Office location object (optional for checkout)
        user_lat: User's latitude
        user_lon: User's longitude
        distance: Distance from office in meters
    """
    result = AttendanceService.record_checkout(
        user_id=user_id,
        location_id=location.id if location else None,
        user_latitude=user_lat,
        user_longitude=user_lon,
        distance=distance
    )
    
    if result.success:
        work_hours = AttendanceService.format_duration(result.work_duration)
        response = Messages.CHECKOUT_SUCCESS.format(
            time=result.attendance_log.timestamp.strftime("%H:%M"),
            work_hours=work_hours
        )
    else:
        response = result.message
    
    await message.reply_text(
        response,
        reply_markup=Keyboards.main_menu()
    )


async def cancel_action(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
) -> None:
    """Handle cancel button press."""
    user_id = update.effective_user.id
    
    # Clear any pending action
    if user_id in pending_actions:
        del pending_actions[user_id]
    
    await update.message.reply_text(
        "Da huy.",
        reply_markup=Keyboards.main_menu()
    )


async def status_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
) -> None:
    """
    Handle /status command.
    
    Shows user's current attendance status for today.
    """
    user_id = update.effective_user.id
    user = UserService.get_user(user_id)
    
    if not user:
        await update.message.reply_text(Messages.ERROR_NOT_REGISTERED)
        return
    
    # Get today's attendance
    attendance = AttendanceService.get_user_attendance_today(user_id)
    
    # Format check-in/out times
    checkin_str = (
        attendance.check_in_time.strftime("%H:%M") 
        if attendance.check_in_time else "Chua check-in"
    )
    checkout_str = (
        attendance.check_out_time.strftime("%H:%M")
        if attendance.check_out_time else "Chua check-out"
    )
    
    # Build status message
    status_text = Messages.STATUS_TEMPLATE.format(
        name=user.full_name,
        role="Admin" if user.is_admin else "Nhan vien",
        status=user.status.value,
        joined_date=user.joined_at.strftime("%d/%m/%Y")
    )
    
    today_text = Messages.TODAY_STATUS.format(
        date=datetime.now().strftime("%d/%m/%Y"),
        checkin_time=checkin_str,
        checkout_time=checkout_str
    )
    
    # Add late info if applicable
    if attendance.is_late:
        today_text += f"\n- Di muon: {attendance.late_minutes} phut"
    
    # Add work duration if checked out
    if attendance.work_duration:
        duration_str = AttendanceService.format_duration(attendance.work_duration)
        today_text += f"\n- Thoi gian lam viec: {duration_str}"
    
    await update.message.reply_text(
        f"{status_text}\n\n{today_text}",
        reply_markup=Keyboards.main_menu()
    )


async def history_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
) -> None:
    """
    Handle /history command.
    
    Shows user's attendance history for the current month.
    """
    user_id = update.effective_user.id
    user = UserService.get_user(user_id)
    
    if not user:
        await update.message.reply_text(Messages.ERROR_NOT_REGISTERED)
        return
    
    # Get current month summary
    now = datetime.now()
    summary = AttendanceService.get_monthly_summary(
        user_id, now.year, now.month
    )
    
    history_text = (
        f"Lich su diem danh thang {now.month}/{now.year}:\n\n"
        f"Tong so ngay: {summary['total_days']}\n"
        f"Di dung gio: {summary['on_time_days']}\n"
        f"Di muon: {summary['late_days']}\n"
        f"Tong phut muon: {summary['total_late_minutes']}\n"
        f"Ti le chuyen can: {summary['attendance_rate']:.1f}%"
    )
    
    await update.message.reply_text(
        history_text,
        reply_markup=Keyboards.main_menu()
    )
```

### Step 3: Create Text Message Handler for Menu Buttons

**File: `src/bot/handlers/menu.py`**

```python
"""
Menu button handler for text messages.

Routes text messages from reply keyboard buttons to appropriate handlers.
"""

from telegram import Update
from telegram.ext import ContextTypes

from src.constants import KeyboardLabels
from src.bot.handlers.checkin import (
    checkin_command,
    checkout_command,
    status_command,
    history_command,
    cancel_action
)


async def text_message_handler(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
) -> None:
    """
    Handle text messages from reply keyboard buttons.
    
    Routes button presses to appropriate handlers.
    """
    text = update.message.text
    
    # Map button labels to handlers
    handlers = {
        KeyboardLabels.CHECKIN: checkin_command,
        "Check-in": checkin_command,
        KeyboardLabels.CHECKOUT: checkout_command,
        "Check-out": checkout_command,
        KeyboardLabels.STATUS: status_command,
        "Trang thai": status_command,
        KeyboardLabels.HISTORY: history_command,
        "Lich su": history_command,
        KeyboardLabels.CANCEL: cancel_action,
        "Huy": cancel_action,
    }
    
    handler = handlers.get(text)
    
    if handler:
        await handler(update, context)
    else:
        # Unknown text, might be conversation input
        # Just ignore or send help
        pass
```

---

## Testing Attendance System

```python
"""Test file: tests/test_attendance.py"""

import pytest
from datetime import datetime, date, time, timedelta
from src.services.attendance import AttendanceService, CheckInResult
from src.database import init_db, User, Location, UserStatus

@pytest.fixture
def setup_db():
    """Initialize test database with sample data."""
    init_db("sqlite:///:memory:")
    
    # Create test user
    from src.services.user_service import UserService
    UserService.create_user(123, "Test User", status=UserStatus.ACTIVE)
    
    # Create test location
    from src.services.geolocation import GeolocationService
    GeolocationService.create_location(
        name="Test Office",
        latitude=21.0285,
        longitude=105.8542,
        radius=50,
        created_by=123
    )
    
    yield

def test_record_checkin(setup_db):
    """Test successful check-in recording."""
    result = AttendanceService.record_checkin(
        user_id=123,
        location_id=1,
        user_latitude=21.0285,
        user_longitude=105.8542,
        distance=10.5
    )
    
    assert result.success == True
    assert result.attendance_log is not None
    assert result.distance == 10.5

def test_duplicate_checkin_blocked(setup_db):
    """Test that duplicate check-ins are blocked."""
    # First check-in
    AttendanceService.record_checkin(
        user_id=123, location_id=1,
        user_latitude=21.0, user_longitude=105.0,
        distance=10
    )
    
    # Second check-in should fail
    result = AttendanceService.record_checkin(
        user_id=123, location_id=1,
        user_latitude=21.0, user_longitude=105.0,
        distance=10
    )
    
    assert result.success == False

def test_checkout_without_checkin(setup_db):
    """Test that checkout fails without check-in."""
    result = AttendanceService.record_checkout(
        user_id=123, location_id=1,
        user_latitude=21.0, user_longitude=105.0,
        distance=10
    )
    
    assert result.success == False
    assert "chua check-in" in result.message.lower()

def test_work_duration_calculation(setup_db):
    """Test work duration calculation on checkout."""
    # Check in
    AttendanceService.record_checkin(
        user_id=123, location_id=1,
        user_latitude=21.0, user_longitude=105.0,
        distance=10
    )
    
    # Check out
    result = AttendanceService.record_checkout(
        user_id=123, location_id=1,
        user_latitude=21.0, user_longitude=105.0,
        distance=10
    )
    
    assert result.success == True
    assert result.work_duration is not None
```

---

## Verification Checklist

Before proceeding to the next blueprint, verify:

- [ ] `src/services/attendance.py` created with all methods
- [ ] `src/bot/handlers/checkin.py` created with handlers
- [ ] `src/bot/handlers/menu.py` created for button routing
- [ ] Check-in flow works: Button -> Location request -> Record
- [ ] Check-out flow works similarly
- [ ] Duplicate check-in/out prevented
- [ ] Late detection works correctly
- [ ] Status command shows today's attendance
- [ ] History command shows monthly summary

---

## Next Steps

Proceed to `05_GEOLOCATION.md` to implement location management and distance calculation.
