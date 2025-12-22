"""Attendance service for Telegram Attendance Bot."""

from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import List, Optional, Tuple

import pytz
from sqlalchemy import func

from src.config import get_config
from src.database import (
    AttendanceLog,
    AttendanceType,
    User,
    UserStatus,
    get_db_session,
)


@dataclass
class CheckInResult:
    """Result of a check-in operation."""

    success: bool
    message: str
    attendance_log: Optional[AttendanceLog]
    is_late: bool
    late_minutes: int
    distance: float


@dataclass
class CheckOutResult:
    """Result of a check-out operation."""

    success: bool
    message: str
    attendance_log: Optional[AttendanceLog]
    work_duration: Optional[timedelta]


@dataclass
class DailyAttendance:
    """Daily attendance summary for a user."""

    user_id: int
    user_name: str
    date: date
    check_in_time: Optional[datetime]
    check_out_time: Optional[datetime]
    is_late: bool
    late_minutes: int
    work_duration: Optional[timedelta]
    status: str


class AttendanceService:
    """Service class for handling attendance operations."""

    @staticmethod
    def get_timezone() -> pytz.BaseTzInfo:
        """
        Get the configured timezone.

        Returns:
            The configured timezone object.
        """
        config = get_config()
        return pytz.timezone(config.timezone.timezone)

    @staticmethod
    def get_current_time() -> datetime:
        """
        Get the current time in the configured timezone.

        Returns:
            Current datetime in configured timezone.
        """
        tz = AttendanceService.get_timezone()
        return datetime.now(tz)

    @staticmethod
    def is_late(check_time: datetime) -> Tuple[bool, int]:
        """
        Check if the given check-in time is late.

        Args:
            check_time: The check-in datetime.

        Returns:
            Tuple of (is_late, minutes_late).
        """
        config = get_config()
        tz = AttendanceService.get_timezone()

        # Ensure check_time is timezone aware
        if check_time.tzinfo is None:
            check_time = tz.localize(check_time)
        else:
            check_time = check_time.astimezone(tz)

        # Create work start time for the same day
        work_start = tz.localize(
            datetime(
                check_time.year,
                check_time.month,
                check_time.day,
                config.attendance.work_start_hour,
                config.attendance.work_start_minute,
                0,
            )
        )

        # Add late threshold
        late_threshold = work_start + timedelta(
            minutes=config.attendance.late_threshold_minutes
        )

        if check_time > late_threshold:
            # Calculate minutes late from work start time
            diff = check_time - work_start
            minutes_late = int(diff.total_seconds() / 60)
            return True, minutes_late

        return False, 0

    @staticmethod
    def has_checked_in_today(
        user_id: int, target_date: Optional[date] = None
    ) -> bool:
        """
        Check if the user has already checked in today.

        Args:
            user_id: The Telegram user ID.
            target_date: The date to check. Defaults to today.

        Returns:
            True if user has checked in, False otherwise.
        """
        if target_date is None:
            target_date = AttendanceService.get_current_time().date()

        with get_db_session() as session:
            log = (
                session.query(AttendanceLog)
                .filter(
                    AttendanceLog.user_id == user_id,
                    AttendanceLog.type == AttendanceType.IN,
                    func.date(AttendanceLog.timestamp) == target_date,
                )
                .first()
            )
            return log is not None

    @staticmethod
    def has_checked_out_today(
        user_id: int, target_date: Optional[date] = None
    ) -> bool:
        """
        Check if the user has already checked out today.

        Args:
            user_id: The Telegram user ID.
            target_date: The date to check. Defaults to today.

        Returns:
            True if user has checked out, False otherwise.
        """
        if target_date is None:
            target_date = AttendanceService.get_current_time().date()

        with get_db_session() as session:
            log = (
                session.query(AttendanceLog)
                .filter(
                    AttendanceLog.user_id == user_id,
                    AttendanceLog.type == AttendanceType.OUT,
                    func.date(AttendanceLog.timestamp) == target_date,
                )
                .first()
            )
            return log is not None

    @staticmethod
    def get_today_checkin(user_id: int) -> Optional[AttendanceLog]:
        """
        Get today's check-in log for a user.

        Args:
            user_id: The Telegram user ID.

        Returns:
            The check-in AttendanceLog or None if not found.
        """
        today = AttendanceService.get_current_time().date()

        with get_db_session() as session:
            log = (
                session.query(AttendanceLog)
                .filter(
                    AttendanceLog.user_id == user_id,
                    AttendanceLog.type == AttendanceType.IN,
                    func.date(AttendanceLog.timestamp) == today,
                )
                .first()
            )
            if log:
                # Detach from session to use outside context
                session.expunge(log)
            return log

    @staticmethod
    def record_checkin(
        user_id: int,
        location_id: int,
        user_lat: float,
        user_lon: float,
        distance: float,
    ) -> CheckInResult:
        """
        Record a check-in for a user.

        Args:
            user_id: The Telegram user ID.
            location_id: The location ID where check-in occurs.
            user_lat: User's latitude.
            user_lon: User's longitude.
            distance: Distance from the location in meters.

        Returns:
            CheckInResult with operation details.
        """
        current_time = AttendanceService.get_current_time()

        # Check if already checked in
        if AttendanceService.has_checked_in_today(user_id):
            return CheckInResult(
                success=False,
                message="You have already checked in today.",
                attendance_log=None,
                is_late=False,
                late_minutes=0,
                distance=distance,
            )

        # Check if late
        is_late, late_minutes = AttendanceService.is_late(current_time)

        with get_db_session() as session:
            # Create attendance log
            attendance_log = AttendanceLog(
                user_id=user_id,
                location_id=location_id,
                type=AttendanceType.IN,
                timestamp=current_time.replace(tzinfo=None),
                user_latitude=user_lat,
                user_longitude=user_lon,
                distance=distance,
                is_late=is_late,
            )
            session.add(attendance_log)
            session.flush()

            # Detach from session
            session.expunge(attendance_log)

        # Build message
        if is_late:
            message = f"Check-in recorded. You are {late_minutes} minutes late."
        else:
            message = "Check-in recorded successfully. You are on time!"

        return CheckInResult(
            success=True,
            message=message,
            attendance_log=attendance_log,
            is_late=is_late,
            late_minutes=late_minutes,
            distance=distance,
        )

    @staticmethod
    def record_checkout(
        user_id: int,
        location_id: int,
        user_lat: float,
        user_lon: float,
        distance: float,
    ) -> CheckOutResult:
        """
        Record a check-out for a user.

        Args:
            user_id: The Telegram user ID.
            location_id: The location ID where check-out occurs.
            user_lat: User's latitude.
            user_lon: User's longitude.
            distance: Distance from the location in meters.

        Returns:
            CheckOutResult with operation details.
        """
        current_time = AttendanceService.get_current_time()

        # Check if already checked out
        if AttendanceService.has_checked_out_today(user_id):
            return CheckOutResult(
                success=False,
                message="You have already checked out today.",
                attendance_log=None,
                work_duration=None,
            )

        # Check if checked in today
        checkin_log = AttendanceService.get_today_checkin(user_id)
        if checkin_log is None:
            return CheckOutResult(
                success=False,
                message="You have not checked in today. Please check in first.",
                attendance_log=None,
                work_duration=None,
            )

        # Calculate work duration
        tz = AttendanceService.get_timezone()
        checkin_time = checkin_log.timestamp
        if checkin_time.tzinfo is None:
            checkin_time = tz.localize(checkin_time)

        work_duration = current_time - checkin_time

        with get_db_session() as session:
            # Create attendance log
            attendance_log = AttendanceLog(
                user_id=user_id,
                location_id=location_id,
                type=AttendanceType.OUT,
                timestamp=current_time.replace(tzinfo=None),
                user_latitude=user_lat,
                user_longitude=user_lon,
                distance=distance,
                is_late=False,
            )
            session.add(attendance_log)
            session.flush()

            # Detach from session
            session.expunge(attendance_log)

        duration_str = AttendanceService.format_duration(work_duration)
        message = f"Check-out recorded successfully. Work duration: {duration_str}"

        return CheckOutResult(
            success=True,
            message=message,
            attendance_log=attendance_log,
            work_duration=work_duration,
        )

    @staticmethod
    def get_user_attendance_today(user_id: int) -> Optional[DailyAttendance]:
        """
        Get today's attendance for a user.

        Args:
            user_id: The Telegram user ID.

        Returns:
            DailyAttendance object or None if no attendance found.
        """
        today = AttendanceService.get_current_time().date()

        with get_db_session() as session:
            # Get user info
            user = session.query(User).filter(User.user_id == user_id).first()
            if user is None:
                return None

            user_name = user.full_name

            # Get check-in log
            checkin_log = (
                session.query(AttendanceLog)
                .filter(
                    AttendanceLog.user_id == user_id,
                    AttendanceLog.type == AttendanceType.IN,
                    func.date(AttendanceLog.timestamp) == today,
                )
                .first()
            )

            # Get check-out log
            checkout_log = (
                session.query(AttendanceLog)
                .filter(
                    AttendanceLog.user_id == user_id,
                    AttendanceLog.type == AttendanceType.OUT,
                    func.date(AttendanceLog.timestamp) == today,
                )
                .first()
            )

            if checkin_log is None:
                return DailyAttendance(
                    user_id=user_id,
                    user_name=user_name,
                    date=today,
                    check_in_time=None,
                    check_out_time=None,
                    is_late=False,
                    late_minutes=0,
                    work_duration=None,
                    status="absent",
                )

            check_in_time = checkin_log.timestamp
            check_out_time = checkout_log.timestamp if checkout_log else None
            is_late = checkin_log.is_late
            late_minutes = 0

            if is_late:
                _, late_minutes = AttendanceService.is_late(check_in_time)

            work_duration = None
            if check_out_time:
                work_duration = check_out_time - check_in_time
                status = "complete"
            else:
                status = "checked_in"

            return DailyAttendance(
                user_id=user_id,
                user_name=user_name,
                date=today,
                check_in_time=check_in_time,
                check_out_time=check_out_time,
                is_late=is_late,
                late_minutes=late_minutes,
                work_duration=work_duration,
                status=status,
            )

    @staticmethod
    def get_all_attendance_today() -> List[DailyAttendance]:
        """
        Get today's attendance for all active users.

        Returns:
            List of DailyAttendance objects for all active users.
        """
        today = AttendanceService.get_current_time().date()
        attendance_list: List[DailyAttendance] = []

        with get_db_session() as session:
            # Get all active users
            active_users = (
                session.query(User)
                .filter(User.status == UserStatus.ACTIVE)
                .all()
            )

            for user in active_users:
                # Get check-in log
                checkin_log = (
                    session.query(AttendanceLog)
                    .filter(
                        AttendanceLog.user_id == user.user_id,
                        AttendanceLog.type == AttendanceType.IN,
                        func.date(AttendanceLog.timestamp) == today,
                    )
                    .first()
                )

                # Get check-out log
                checkout_log = (
                    session.query(AttendanceLog)
                    .filter(
                        AttendanceLog.user_id == user.user_id,
                        AttendanceLog.type == AttendanceType.OUT,
                        func.date(AttendanceLog.timestamp) == today,
                    )
                    .first()
                )

                if checkin_log is None:
                    attendance_list.append(
                        DailyAttendance(
                            user_id=user.user_id,
                            user_name=user.full_name,
                            date=today,
                            check_in_time=None,
                            check_out_time=None,
                            is_late=False,
                            late_minutes=0,
                            work_duration=None,
                            status="absent",
                        )
                    )
                else:
                    check_in_time = checkin_log.timestamp
                    check_out_time = checkout_log.timestamp if checkout_log else None
                    is_late = checkin_log.is_late
                    late_minutes = 0

                    if is_late:
                        _, late_minutes = AttendanceService.is_late(check_in_time)

                    work_duration = None
                    if check_out_time:
                        work_duration = check_out_time - check_in_time
                        status = "complete"
                    else:
                        status = "checked_in"

                    attendance_list.append(
                        DailyAttendance(
                            user_id=user.user_id,
                            user_name=user.full_name,
                            date=today,
                            check_in_time=check_in_time,
                            check_out_time=check_out_time,
                            is_late=is_late,
                            late_minutes=late_minutes,
                            work_duration=work_duration,
                            status=status,
                        )
                    )

        return attendance_list

    @staticmethod
    def get_user_attendance_history(
        user_id: int, start_date: date, end_date: date
    ) -> List[AttendanceLog]:
        """
        Get attendance history for a user within a date range.

        Args:
            user_id: The Telegram user ID.
            start_date: Start date of the range.
            end_date: End date of the range.

        Returns:
            List of AttendanceLog objects.
        """
        with get_db_session() as session:
            logs = (
                session.query(AttendanceLog)
                .filter(
                    AttendanceLog.user_id == user_id,
                    func.date(AttendanceLog.timestamp) >= start_date,
                    func.date(AttendanceLog.timestamp) <= end_date,
                )
                .order_by(AttendanceLog.timestamp.asc())
                .all()
            )

            # Detach from session
            for log in logs:
                session.expunge(log)

            return logs

    @staticmethod
    def get_monthly_summary(user_id: int, year: int, month: int) -> dict:
        """
        Get monthly attendance summary for a user.

        Args:
            user_id: The Telegram user ID.
            year: The year.
            month: The month (1-12).

        Returns:
            Dictionary with monthly statistics including:
            - total_days: Total working days
            - present_days: Days with attendance
            - late_days: Days marked as late
            - absent_days: Days without attendance
            - total_work_hours: Total hours worked
            - average_work_hours: Average hours per day
        """
        from calendar import monthrange

        # Get start and end date of the month
        _, last_day = monthrange(year, month)
        start_date = date(year, month, 1)
        end_date = date(year, month, last_day)

        # Get today's date to not count future days
        today = AttendanceService.get_current_time().date()
        if end_date > today:
            end_date = today

        with get_db_session() as session:
            # Get all check-in logs for the month - extract data immediately
            checkin_results = (
                session.query(
                    AttendanceLog.timestamp,
                    AttendanceLog.is_late
                )
                .filter(
                    AttendanceLog.user_id == user_id,
                    AttendanceLog.type == AttendanceType.IN,
                    func.date(AttendanceLog.timestamp) >= start_date,
                    func.date(AttendanceLog.timestamp) <= end_date,
                )
                .all()
            )
            
            # Extract to plain Python data
            checkin_data = [(row.timestamp, row.is_late) for row in checkin_results]

            # Get all check-out logs for the month - extract data immediately
            checkout_results = (
                session.query(AttendanceLog.timestamp)
                .filter(
                    AttendanceLog.user_id == user_id,
                    AttendanceLog.type == AttendanceType.OUT,
                    func.date(AttendanceLog.timestamp) >= start_date,
                    func.date(AttendanceLog.timestamp) <= end_date,
                )
                .all()
            )
            
            # Extract to plain Python data
            checkout_data = [row.timestamp for row in checkout_results]

        # All processing now uses plain Python data (outside session is OK)
        # Build checkout lookup by date
        checkout_by_date = {}
        for ts in checkout_data:
            log_date = ts.date()
            checkout_by_date[log_date] = ts

        # Calculate statistics
        present_days = len(checkin_data)
        late_days = sum(1 for _, is_late in checkin_data if is_late)

        # Calculate total work hours
        total_work_seconds = 0
        for checkin_ts, _ in checkin_data:
            checkin_date = checkin_ts.date()
            checkout_time = checkout_by_date.get(checkin_date)
            if checkout_time:
                duration = checkout_time - checkin_ts
                total_work_seconds += duration.total_seconds()

        total_work_hours = total_work_seconds / 3600

        # Calculate working days (exclude weekends - Saturday=5, Sunday=6)
        total_days = 0
        current = start_date
        while current <= end_date:
            if current.weekday() < 5:  # Monday to Friday
                total_days += 1
            current += timedelta(days=1)

        absent_days = total_days - present_days

        # Calculate average work hours
        average_work_hours = total_work_hours / present_days if present_days > 0 else 0

        return {
            "total_days": total_days,
            "present_days": present_days,
            "late_days": late_days,
            "absent_days": absent_days,
            "total_work_hours": round(total_work_hours, 2),
            "average_work_hours": round(average_work_hours, 2),
        }

    @staticmethod
    def format_duration(duration: timedelta) -> str:
        """
        Format a timedelta as a human-readable string.

        Args:
            duration: The timedelta to format.

        Returns:
            Formatted string like "8h 30m".
        """
        total_seconds = int(duration.total_seconds())
        hours = total_seconds // 3600
        minutes = (total_seconds % 3600) // 60

        if hours > 0 and minutes > 0:
            return f"{hours}h {minutes}m"
        elif hours > 0:
            return f"{hours}h"
        else:
            return f"{minutes}m"
