"""Attendance service for check-in/check-out with point system."""

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Optional, Tuple

import pytz
from sqlalchemy import func

from src.config import get_config
from src.database import (
    AttendanceLog,
    AttendanceType,
    Meeting,
    User,
    UserStatus,
    get_db_session,
)
from src.services.point_service import PointService


@dataclass
class CheckInResult:
    """Result of a check-in operation."""
    success: bool
    message: str
    attendance_log: Optional[AttendanceLog]
    meeting: Optional[Meeting]


@dataclass
class CheckOutResult:
    """Result of a check-out operation."""
    success: bool
    message: str
    attendance_log: Optional[AttendanceLog]
    meeting: Optional[Meeting]
    points_earned: int


class AttendanceService:
    """Service class for handling attendance operations."""

    @staticmethod
    def get_timezone() -> pytz.BaseTzInfo:
        """Get the configured timezone."""
        config = get_config()
        return pytz.timezone(config.timezone.timezone)

    @staticmethod
    def get_current_time() -> datetime:
        """Get the current time in the configured timezone."""
        tz = AttendanceService.get_timezone()
        return datetime.now(tz)

    @staticmethod
    def has_checked_in(user_id: int, meeting_id: int) -> bool:
        """Check if user has checked in for a meeting."""
        with get_db_session() as session:
            log = session.query(AttendanceLog).filter(
                AttendanceLog.user_id == user_id,
                AttendanceLog.meeting_id == meeting_id,
                AttendanceLog.type == AttendanceType.IN,
            ).first()
            return log is not None

    @staticmethod
    def has_checked_out(user_id: int, meeting_id: int) -> bool:
        """Check if user has checked out for a meeting."""
        with get_db_session() as session:
            log = session.query(AttendanceLog).filter(
                AttendanceLog.user_id == user_id,
                AttendanceLog.meeting_id == meeting_id,
                AttendanceLog.type == AttendanceType.OUT,
            ).first()
            return log is not None

    @staticmethod
    def get_checkin_log(user_id: int, meeting_id: int) -> Optional[AttendanceLog]:
        """Get check-in log for a user and meeting."""
        with get_db_session() as session:
            log = session.query(AttendanceLog).filter(
                AttendanceLog.user_id == user_id,
                AttendanceLog.meeting_id == meeting_id,
                AttendanceType.IN == AttendanceLog.type,
            ).first()
            if log:
                session.expunge(log)
            return log

    @staticmethod
    def record_checkin(user_id: int, meeting_id: int) -> CheckInResult:
        """
        Record a check-in for a user.
        
        Args:
            user_id: The Telegram user ID
            meeting_id: The meeting ID
        """
        # Check if already checked in
        if AttendanceService.has_checked_in(user_id, meeting_id):
            return CheckInResult(
                success=False,
                message="Bạn đã điểm danh buổi họp này rồi!",
                attendance_log=None,
                meeting=None,
            )

        current_time = AttendanceService.get_current_time()

        with get_db_session() as session:
            # Get meeting info
            meeting = session.query(Meeting).filter(
                Meeting.id == meeting_id
            ).first()
            
            if not meeting:
                return CheckInResult(
                    success=False,
                    message="Không tìm thấy buổi họp!",
                    attendance_log=None,
                    meeting=None,
                )

            # Create attendance log
            attendance_log = AttendanceLog(
                user_id=user_id,
                meeting_id=meeting_id,
                type=AttendanceType.IN,
                timestamp=current_time.replace(tzinfo=None),
            )
            session.add(attendance_log)
            session.flush()
            session.expunge(attendance_log)
            session.expunge(meeting)

        return CheckInResult(
            success=True,
            message="Điểm danh thành công!",
            attendance_log=attendance_log,
            meeting=meeting,
        )

    @staticmethod
    def record_checkout(user_id: int, meeting_id: int) -> CheckOutResult:
        """
        Record a check-out for a user.
        Only gives points if both check-in and check-out are completed.
        
        Args:
            user_id: The Telegram user ID
            meeting_id: The meeting ID
        """
        # Check if checked in
        if not AttendanceService.has_checked_in(user_id, meeting_id):
            return CheckOutResult(
                success=False,
                message="Bạn chưa điểm danh buổi họp này!",
                attendance_log=None,
                meeting=None,
                points_earned=0,
            )

        # Check if already checked out
        if AttendanceService.has_checked_out(user_id, meeting_id):
            return CheckOutResult(
                success=False,
                message="Bạn đã check-out rồi!",
                attendance_log=None,
                meeting=None,
                points_earned=0,
            )

        current_time = AttendanceService.get_current_time()
        current_naive = current_time.replace(tzinfo=None)

        with get_db_session() as session:
            # Get meeting info
            meeting = session.query(Meeting).filter(
                Meeting.id == meeting_id
            ).first()
            
            if not meeting:
                return CheckOutResult(
                    success=False,
                    message="Không tìm thấy buổi họp!",
                    attendance_log=None,
                    meeting=None,
                    points_earned=0,
                )

            # Ensure meeting still active for checkout
            if meeting.end_time and meeting.end_time < current_naive:
                return CheckOutResult(
                    success=False,
                    message="Buoi hop da ket thuc. Khong the check-out.",
                    attendance_log=None,
                    meeting=meeting,
                    points_earned=0,
                )

            # Check duration from checkin
            checkin_log = session.query(AttendanceLog).filter(
                AttendanceLog.user_id == user_id,
                AttendanceLog.meeting_id == meeting_id,
                AttendanceLog.type == AttendanceType.IN,
            ).order_by(AttendanceLog.timestamp.asc()).first()
            
            if not checkin_log:
                return CheckOutResult(
                    success=False,
                    message="Chua co log check-in!",
                    attendance_log=None,
                    meeting=meeting,
                    points_earned=0,
                )
            
            duration = current_naive - checkin_log.timestamp
            if duration.total_seconds() < 30 * 60:
                minutes_left = int((30 * 60 - duration.total_seconds()) // 60) + 1
                return CheckOutResult(
                    success=False,
                    message=f"Can cho it nhat 30 phut sau check-in moi duoc check-out. Con {minutes_left} phut.",
                    attendance_log=None,
                    meeting=meeting,
                    points_earned=0,
                )

            # Create checkout log
            attendance_log = AttendanceLog(
                user_id=user_id,
                meeting_id=meeting_id,
                type=AttendanceType.OUT,
                timestamp=current_naive,
                duration_minutes=duration.total_seconds() / 60.0,
            )
            session.add(attendance_log)
            
            points = meeting.points
            meeting_title = meeting.title
            
            session.flush()
            session.expunge(attendance_log)
            session.expunge(meeting)

        # Cộng điểm cho user (chỉ khi checkout đầy đủ)
        PointService.add_points(
            user_id=user_id,
            points=points,
            reason=f"Tham gia: {meeting_title}",
            source_type="meeting",
            source_id=meeting_id,
        )

        return CheckOutResult(
            success=True,
            message=f"Check-out thành công! +{points} điểm",
            attendance_log=attendance_log,
            meeting=meeting,
            points_earned=points,
        )

    @staticmethod
    def get_meeting_attendance(meeting_id: int) -> list:
        """Get all attendance logs for a meeting."""
        with get_db_session() as session:
            logs = session.query(AttendanceLog).filter(
                AttendanceLog.meeting_id == meeting_id
            ).order_by(AttendanceLog.timestamp.asc()).all()
            
            for log in logs:
                session.expunge(log)
            return logs

    @staticmethod
    def format_duration(duration: timedelta) -> str:
        """Format a timedelta as a human-readable string."""
        total_seconds = int(duration.total_seconds())
        hours = total_seconds // 3600
        minutes = (total_seconds % 3600) // 60

        if hours > 0 and minutes > 0:
            return f"{hours}h {minutes}m"
        elif hours > 0:
            return f"{hours}h"
        else:
            return f"{minutes}m"

    @staticmethod
    def penalize_no_checkin(user_id: int, meeting_id: int) -> None:
        """Trừ điểm vì không đạt bài quy chế check-in (-3 điểm)."""
        PointService.add_points(
            user_id=user_id,
            points=-3,
            reason="Không đạt bài quy chế check-in",
            source_type="penalty",
            source_id=meeting_id,
        )

    @staticmethod
    def get_total_minutes(user_id: int) -> float:
        """Tổng số phút họp đã check-out (cộng dồn)."""
        with get_db_session() as session:
            total = session.query(func.sum(AttendanceLog.duration_minutes)).filter(
                AttendanceLog.user_id == user_id,
                AttendanceLog.type == AttendanceType.OUT,
            ).scalar()
            return float(total or 0)

    @staticmethod
    def penalize_absence(user_id: int, meeting_id: int) -> None:
        """Trừ điểm vì đăng ký nhưng không tham gia (-10 điểm)."""
        PointService.add_points(
            user_id=user_id,
            points=-10,
            reason="Đăng ký nhưng không tham gia (không có lý do)",
            source_type="absence",
            source_id=meeting_id,
        )
