"""Point service - Quản lý điểm số và xếp hạng."""

from dataclasses import dataclass
from datetime import datetime
from typing import List, Optional, Tuple

from sqlalchemy import func

from src.database import (
    PointLog,
    User,
    UserStatus,
    WarningLevel,
    get_db_session,
)


# Ngưỡng điểm để nâng cảnh báo
LOW_POINT_THRESHOLD = 15  # Dưới 15 điểm = cảnh báo
CONSECUTIVE_LOW_MONTHS = 2  # Số tháng liên tiếp dưới ngưỡng để nâng band cảnh báo


@dataclass
class UserPointSummary:
    """Tổng hợp điểm của user."""
    user_id: int
    user_name: str
    monthly_points: int  # Điểm tháng hiện tại
    total_points: int    # Tổng điểm kỳ
    rank: int            # Thứ hạng
    warning_level: WarningLevel
    cc_level: str        # Mức CC: adudu, can_than, cook


class PointService:
    """Service quản lý điểm số."""

    @staticmethod
    def get_current_month_year() -> Tuple[int, int]:
        """Lấy tháng và năm hiện tại."""
        now = datetime.now()
        return now.month, now.year

    @staticmethod
    def add_points(
        user_id: int,
        points: int,
        reason: str,
        source_type: str,
        source_id: Optional[int] = None
    ) -> PointLog:
        """
        Thêm điểm cho user.
        
        Args:
            user_id: ID người dùng
            points: Số điểm (dương = cộng, âm = trừ)
            reason: Lý do
            source_type: Loại nguồn ('meeting', 'evidence', 'penalty', 'absence')
            source_id: ID nguồn (meeting_id hoặc evidence_id)
        """
        month, year = PointService.get_current_month_year()
        
        with get_db_session() as session:
            point_log = PointLog(
                user_id=user_id,
                points=points,
                reason=reason,
                source_type=source_type,
                source_id=source_id,
                month=month,
                year=year,
            )
            session.add(point_log)
            session.flush()
            session.expunge(point_log)
            return point_log

    @staticmethod
    def get_user_monthly_points(user_id: int, month: int = None, year: int = None) -> int:
        """Lấy tổng điểm tháng của user."""
        if month is None or year is None:
            month, year = PointService.get_current_month_year()
        
        with get_db_session() as session:
            result = session.query(func.sum(PointLog.points)).filter(
                PointLog.user_id == user_id,
                PointLog.month == month,
                PointLog.year == year,
            ).scalar()
            return result or 0

    @staticmethod
    def get_user_total_points(user_id: int, year: int = None) -> int:
        """Lấy tổng điểm cả kỳ (năm) của user."""
        if year is None:
            _, year = PointService.get_current_month_year()
        
        with get_db_session() as session:
            result = session.query(func.sum(PointLog.points)).filter(
                PointLog.user_id == user_id,
                PointLog.year == year,
            ).scalar()
            return result or 0

    @staticmethod
    def get_cc_level(monthly_points: int) -> str:
        """
        (Legacy) Xác định mức CC dựa trên điểm tháng.
        Giữ lại cho tương thích; dùng get_monthly_cc_display cho UI.
        """
        if monthly_points < 10:
            return "adudu"
        elif monthly_points <= 20:
            return "can_than"
        else:
            return "cook"

    @staticmethod
    def get_cc_level_display(cc_level: str) -> str:
        """Hiển thị mức CC."""
        displays = {
            "adudu": "🔴 Tôi là Adudu",
            "can_than": "🟡 Cẩn thận",
            "cook": "🟢 Đang Cook",
        }
        return displays.get(cc_level, "❓ Unknown")

    @staticmethod
    def get_monthly_cc_display(monthly_points: int) -> str:
        """
        Mức CC tháng: dưới 15 điểm => Cẩn thận, ngược lại Ổn định.
        """
        if monthly_points < LOW_POINT_THRESHOLD:
            return "⚠️ Cẩn thận (<15đ)"
        return "✅ Ổn định (>=15đ)"

    @staticmethod
    def get_term_cc_display(warning_level: WarningLevel) -> str:
        """
        Mức CC kỳ (band cảnh báo): CC0/1/2/3 dựa trên warning_level.
        """
        mapping = {
            WarningLevel.NONE: "CC0",
            WarningLevel.REMIND: "CC1",
            WarningLevel.DISCIPLINE: "CC2",
            WarningLevel.OUT: "CC3",
        }
        return mapping.get(warning_level, "CC0")

    @staticmethod
    def get_warning_display(warning_level: WarningLevel) -> str:
        """Hiển thị mức cảnh báo."""
        displays = {
            WarningLevel.NONE: "✅ Không có",
            WarningLevel.REMIND: "⚠️ Nhắc nhở",
            WarningLevel.DISCIPLINE: "🚨 Kỷ luật",
            WarningLevel.OUT: "❌ OUT",
        }
        return displays.get(warning_level, "❓ Unknown")

    @staticmethod
    def get_rank_title(rank: int) -> str:
        """Lấy title theo rank."""
        if rank == 1:
            return "👑 Vua Hải Tặc"
        elif rank == 2:
            return "🥈 Phó Vương"
        elif rank == 3:
            return "🥉 Tam Đại Tướng"
        elif rank <= 5:
            return "⭐ Thất Vũ Hải"
        elif rank <= 10:
            return "💪 Supernova"
        else:
            return "🏴‍☠️ Hải Tặc"

    @staticmethod
    def get_all_rankings(month: int = None, year: int = None) -> List[UserPointSummary]:
        """Lấy bảng xếp hạng tất cả users."""
        if month is None or year is None:
            month, year = PointService.get_current_month_year()
        
        with get_db_session() as session:
            # Lấy tất cả user active
            users = session.query(User).filter(
                User.status == UserStatus.ACTIVE
            ).all()
            
            rankings = []
            for user in users:
                # Điểm tháng
                monthly = session.query(func.sum(PointLog.points)).filter(
                    PointLog.user_id == user.user_id,
                    PointLog.month == month,
                    PointLog.year == year,
                ).scalar() or 0
                
                # Điểm năm (tổng kỳ)
                total = session.query(func.sum(PointLog.points)).filter(
                    PointLog.user_id == user.user_id,
                    PointLog.year == year,
                ).scalar() or 0
                
                cc_level = PointService.get_cc_level(monthly)
                
                rankings.append(UserPointSummary(
                    user_id=user.user_id,
                    user_name=user.full_name,
                    monthly_points=monthly,
                    total_points=total,
                    rank=0,  # Sẽ tính sau
                    warning_level=user.warning_level,
                    cc_level=cc_level,
                ))
            
            # Sắp xếp theo điểm tổng kỳ giảm dần
            rankings.sort(key=lambda x: x.total_points, reverse=True)
            
            # Gán rank
            for i, r in enumerate(rankings):
                r.rank = i + 1
            
            return rankings

    @staticmethod
    def get_user_ranking(user_id: int) -> Optional[UserPointSummary]:
        """Lấy thông tin xếp hạng của một user."""
        rankings = PointService.get_all_rankings()
        for r in rankings:
            if r.user_id == user_id:
                return r
        return None

    @staticmethod
    def check_and_update_warnings() -> List[Tuple[int, WarningLevel, WarningLevel]]:
        """
        Kiểm tra và cập nhật mức cảnh báo cuối tháng.
        Điều kiện: 2 tháng liên tiếp dưới ngưỡng LOW_POINT_THRESHOLD mới nâng 1 band.
        Trả về list (user_id, old_level, new_level) của những user bị nâng cảnh báo.
        """
        month, year = PointService.get_current_month_year()
        updated = []
        
        with get_db_session() as session:
            users = session.query(User).filter(
                User.status == UserStatus.ACTIVE
            ).all()
            
            for user in users:
                current_points = PointService._get_month_points(session, user.user_id, month, year)
                
                # Tính tháng trước
                if month == 1:
                    prev_month, prev_year = 12, year - 1
                else:
                    prev_month, prev_year = month - 1, year
                
                prev_points = PointService._get_month_points(session, user.user_id, prev_month, prev_year)
                
                # Nâng band chỉ khi 2 tháng liên tiếp dưới ngưỡng
                if current_points < LOW_POINT_THRESHOLD and prev_points < LOW_POINT_THRESHOLD:
                    old_level = user.warning_level
                    new_level = PointService._get_next_warning_level(old_level)
                    
                    if new_level != old_level:
                        user.warning_level = new_level
                        updated.append((user.user_id, old_level, new_level))
            
            session.commit()
        
        return updated

    @staticmethod
    def _get_next_warning_level(current: WarningLevel) -> WarningLevel:
        """Lấy mức cảnh báo tiếp theo."""
        progression = {
            WarningLevel.NONE: WarningLevel.REMIND,
            WarningLevel.REMIND: WarningLevel.DISCIPLINE,
            WarningLevel.DISCIPLINE: WarningLevel.OUT,
            WarningLevel.OUT: WarningLevel.OUT,
        }
        return progression.get(current, WarningLevel.REMIND)

    @staticmethod
    def _get_month_points(session, user_id: int, month: int, year: int) -> int:
        """Helper: tổng điểm của user theo tháng/năm."""
        return (
            session.query(func.sum(PointLog.points))
            .filter(
                PointLog.user_id == user_id,
                PointLog.month == month,
                PointLog.year == year,
            )
            .scalar()
            or 0
        )

    @staticmethod
    def get_point_history(user_id: int, limit: int = 20) -> List[PointLog]:
        """Lấy lịch sử điểm của user."""
        with get_db_session() as session:
            logs = session.query(PointLog).filter(
                PointLog.user_id == user_id
            ).order_by(PointLog.created_at.desc()).limit(limit).all()
            
            for log in logs:
                session.expunge(log)
            return logs
