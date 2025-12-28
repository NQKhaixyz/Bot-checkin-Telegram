"""Meeting service - Quản lý lịch họp và thông báo."""

import math
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import List, Optional, Tuple

from sqlalchemy import and_

from src.database import (
    Meeting,
    MeetingType,
    MeetingRegistration,
    MEETING_POINTS,
    User,
    UserStatus,
    get_db_session,
)


@dataclass
class MeetingInfo:
    """Thông tin meeting."""
    id: int
    title: str
    location: str
    meeting_type: MeetingType
    points: int
    meeting_time: datetime
    is_active: bool


class MeetingService:
    """Service quản lý lịch họp."""

    # Earth's radius in meters (for haversine calculation)
    EARTH_RADIUS_METERS = 6_371_000

    @staticmethod
    def haversine_distance(
        lat1: float,
        lon1: float,
        lat2: float,
        lon2: float,
    ) -> float:
        """
        Calculate the great-circle distance between two GPS coordinates.

        Uses the Haversine formula to account for Earth's curvature.

        Args:
            lat1: Latitude of point 1 (degrees)
            lon1: Longitude of point 1 (degrees)
            lat2: Latitude of point 2 (degrees)
            lon2: Longitude of point 2 (degrees)

        Returns:
            Distance in meters
        """
        # Convert degrees to radians
        lat1_rad = math.radians(lat1)
        lat2_rad = math.radians(lat2)
        lon1_rad = math.radians(lon1)
        lon2_rad = math.radians(lon2)

        # Differences
        delta_lat = lat2_rad - lat1_rad
        delta_lon = lon2_rad - lon1_rad

        # Haversine formula
        a = (
            math.sin(delta_lat / 2) ** 2
            + math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(delta_lon / 2) ** 2
        )
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

        # Distance in meters
        distance = MeetingService.EARTH_RADIUS_METERS * c

        return distance

    @staticmethod
    def check_location_for_meeting(
        meeting_id: int,
        user_lat: float,
        user_lon: float,
    ) -> Tuple[bool, float]:
        """
        Check if user location is within meeting's geofence.

        Args:
            meeting_id: ID of the meeting
            user_lat: User's latitude
            user_lon: User's longitude

        Returns:
            Tuple of (is_within_radius, distance_meters)
            Returns (False, 0.0) if meeting not found or has no GPS coordinates
        """
        meeting = MeetingService.get_meeting(meeting_id)

        if not meeting:
            return (False, 0.0)

        # Check if meeting has GPS coordinates
        if meeting.latitude is None or meeting.longitude is None:
            return (False, 0.0)

        # Calculate distance
        distance = MeetingService.haversine_distance(
            user_lat, user_lon, meeting.latitude, meeting.longitude
        )

        # Get radius (default 50m if not set)
        radius = meeting.radius if meeting.radius else 50.0

        is_within = distance <= radius
        return (is_within, distance)

    @staticmethod
    def create_meeting(
        title: str,
        location: str,
        meeting_time: datetime,
        end_time: datetime,
        meeting_type: MeetingType = MeetingType.REGULAR,
        created_by: int = None,
        location_id: Optional[int] = None,
        latitude: float = None,
        longitude: float = None,
        radius: float = 50.0,
    ) -> Meeting:
        """
        Tạo lịch họp mới.
        
        Args:
            title: Tiêu đề
            location: Địa điểm
            meeting_time: Thời gian họp
            meeting_type: Loại họp (regular/support/event)
            created_by: ID admin tạo
            location_id: ID địa điểm (locations.id) nếu dùng địa điểm có sẵn
            latitude: GPS latitude coordinate
            longitude: GPS longitude coordinate
            radius: Geofence radius in meters (default 50m)
        """
        points = MEETING_POINTS.get(meeting_type, 5)
        
        with get_db_session() as session:
            meeting = Meeting(
                title=title,
                location=location,
                meeting_type=meeting_type,
                points=points,
                meeting_time=meeting_time,
                end_time=end_time,
                created_by=created_by,
                location_id=location_id,
                latitude=latitude,
                longitude=longitude,
                radius=radius,
            )
            session.add(meeting)
            session.flush()
            session.expunge(meeting)
            return meeting

    @staticmethod
    def get_meeting(meeting_id: int) -> Optional[Meeting]:
        """Lấy meeting theo ID."""
        with get_db_session() as session:
            meeting = session.query(Meeting).filter(
                Meeting.id == meeting_id
            ).first()
            if meeting:
                session.expunge(meeting)
            return meeting

    @staticmethod
    def get_active_meeting() -> Optional[Meeting]:
        """Lấy meeting đang diễn ra (start <= now <= end)."""
        now = datetime.now()
        with get_db_session() as session:
            session.query(Meeting).filter(Meeting.is_active == True, Meeting.end_time < now).update({"is_active": False})
            meeting = session.query(Meeting).filter(
                Meeting.is_active == True,
                Meeting.meeting_time <= now,
                Meeting.end_time >= now,
            ).order_by(Meeting.meeting_time.asc()).first()
            
            if meeting:
                session.expunge(meeting)
            return meeting

    @staticmethod
    def get_active_meetings(now: datetime) -> List[Meeting]:
        """Lấy danh sách meeting đang diễn ra tại thời điểm now."""
        with get_db_session() as session:
            session.query(Meeting).filter(Meeting.is_active == True, Meeting.end_time < now).update({"is_active": False})
            meetings = session.query(Meeting).filter(
                Meeting.is_active == True,
                Meeting.meeting_time <= now,
                Meeting.end_time >= now,
            ).order_by(Meeting.meeting_time.asc()).all()
            for m in meetings:
                session.expunge(m)
            return meetings

    @staticmethod
    def get_upcoming_meetings(days: int = 7) -> List[Meeting]:
        """Lấy danh sách meeting sắp tới."""
        now = datetime.now()
        end_date = now + timedelta(days=days)
        
        with get_db_session() as session:
            session.query(Meeting).filter(Meeting.is_active == True, Meeting.end_time < now).update({"is_active": False})
            meetings = session.query(Meeting).filter(
                Meeting.is_active == True,
                Meeting.end_time >= now,
                Meeting.meeting_time <= end_date,
            ).order_by(Meeting.meeting_time.asc()).all()
            
            for m in meetings:
                session.expunge(m)
            return meetings

    @staticmethod
    def get_all_meetings(include_inactive: bool = False) -> List[Meeting]:
        """Lấy tất cả meetings."""
        with get_db_session() as session:
            query = session.query(Meeting)
            if not include_inactive:
                query = query.filter(Meeting.is_active == True)
            meetings = query.order_by(Meeting.meeting_time.desc()).all()
            
            for m in meetings:
                session.expunge(m)
            return meetings

    @staticmethod
    def deactivate_meeting(meeting_id: int) -> bool:
        """Vô hiệu hóa meeting."""
        with get_db_session() as session:
            meeting = session.query(Meeting).filter(
                Meeting.id == meeting_id
            ).first()
            if meeting:
                meeting.is_active = False
                session.commit()
                return True
            return False

    @staticmethod
    def delete_meeting(meeting_id: int) -> bool:
        """Delete (soft) a meeting by marking inactive."""
        return MeetingService.deactivate_meeting(meeting_id)

    @staticmethod
    def mark_notified(meeting_id: int) -> bool:
        """Đánh dấu đã gửi thông báo."""
        with get_db_session() as session:
            meeting = session.query(Meeting).filter(
                Meeting.id == meeting_id
            ).first()
            if meeting:
                meeting.notified = True
                session.commit()
                return True
            return False

    @staticmethod
    def register_user(meeting_id: int, user_id: int) -> Optional[MeetingRegistration]:
        """Đăng ký user tham gia meeting."""
        with get_db_session() as session:
            # Kiểm tra đã đăng ký chưa
            existing = session.query(MeetingRegistration).filter(
                MeetingRegistration.meeting_id == meeting_id,
                MeetingRegistration.user_id == user_id,
            ).first()
            
            if existing:
                return None
            
            reg = MeetingRegistration(
                user_id=user_id,
                meeting_id=meeting_id,
            )
            session.add(reg)
            session.flush()
            session.expunge(reg)
            return reg

    @staticmethod
    def get_registration(meeting_id: int, user_id: int) -> Optional[MeetingRegistration]:
        """Lấy đăng ký của user cho meeting."""
        with get_db_session() as session:
            reg = session.query(MeetingRegistration).filter(
                MeetingRegistration.meeting_id == meeting_id,
                MeetingRegistration.user_id == user_id,
            ).first()
            if reg:
                session.expunge(reg)
            return reg

    @staticmethod
    def mark_attended(meeting_id: int, user_id: int) -> bool:
        """Đánh dấu đã tham gia."""
        with get_db_session() as session:
            reg = session.query(MeetingRegistration).filter(
                MeetingRegistration.meeting_id == meeting_id,
                MeetingRegistration.user_id == user_id,
            ).first()
            if reg:
                reg.attended = True
                session.commit()
                return True
            return False

    @staticmethod
    def set_absence_reason(meeting_id: int, user_id: int, reason: str) -> bool:
        """Cập nhật lý do vắng mặt."""
        with get_db_session() as session:
            reg = session.query(MeetingRegistration).filter(
                MeetingRegistration.meeting_id == meeting_id,
                MeetingRegistration.user_id == user_id,
            ).first()
            if reg:
                reg.absence_reason = reason
                session.commit()
                return True
            return False

    @staticmethod
    def get_meeting_registrations(meeting_id: int) -> List[MeetingRegistration]:
        """Lấy danh sách đăng ký của meeting."""
        with get_db_session() as session:
            regs = session.query(MeetingRegistration).filter(
                MeetingRegistration.meeting_id == meeting_id
            ).all()
            for r in regs:
                session.expunge(r)
            return regs

    @staticmethod
    def get_users_to_notify() -> List[User]:
        """Lấy danh sách users để gửi thông báo."""
        with get_db_session() as session:
            users = session.query(User).filter(
                User.status == UserStatus.ACTIVE
            ).all()
            for u in users:
                session.expunge(u)
            return users

    @staticmethod
    def get_meeting_type_display(meeting_type: MeetingType) -> str:
        """Hiển thị loại meeting."""
        displays = {
            MeetingType.REGULAR: "📋 Họp thường (C1-101)",
            MeetingType.SUPPORT: "🎤 Hỗ trợ diễn giả",
            MeetingType.EVENT: "🎉 Hoạt động ngoại khóa",
        }
        return displays.get(meeting_type, "📋 Họp")

    @staticmethod
    def format_meeting_info(meeting: Meeting) -> str:
        """Format thông tin meeting."""
        type_display = MeetingService.get_meeting_type_display(meeting.meeting_type)
        time_str = meeting.meeting_time.strftime("%H:%M %d/%m/%Y")
        
        info = (
            f"📌 {meeting.title}\n"
            f"📍 Địa điểm: {meeting.location}\n"
            f"🕐 Thời gian: {time_str}\n"
            f"📊 Loại: {type_display}\n"
            f"⭐ Điểm: +{meeting.points}"
        )
        
        # Add GPS coordinates if available
        if meeting.latitude is not None and meeting.longitude is not None:
            lat_dir = "N" if meeting.latitude >= 0 else "S"
            lon_dir = "E" if meeting.longitude >= 0 else "W"
            coords = f"{abs(meeting.latitude):.4f}°{lat_dir}, {abs(meeting.longitude):.4f}°{lon_dir}"
            radius_str = f"{meeting.radius:.0f}m" if meeting.radius else "50m"
            info += f"\n🌐 GPS: {coords} (bán kính {radius_str})"
        
        return info
