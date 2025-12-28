"""Evidence service - Quản lý minh chứng công việc."""

from dataclasses import dataclass
from datetime import datetime
from typing import List, Optional

from src.database import (
    Evidence,
    EvidenceStatus,
    get_db_session,
)
from src.services.point_service import PointService


@dataclass
class EvidenceInfo:
    """Thông tin minh chứng."""
    id: int
    user_id: int
    user_name: str
    description: str
    photo_file_id: str
    requested_points: int
    status: EvidenceStatus
    review_reason: Optional[str]
    created_at: datetime


class EvidenceService:
    """Service quản lý minh chứng công việc."""

    @staticmethod
    def create_evidence(
        user_id: int,
        description: str,
        photo_file_id: str,
        requested_points: int,
    ) -> Evidence:
        """
        Tạo minh chứng mới.
        
        Args:
            user_id: ID người dùng
            description: Mô tả công việc
            photo_file_id: File ID của ảnh
            requested_points: Số điểm yêu cầu
        """
        with get_db_session() as session:
            evidence = Evidence(
                user_id=user_id,
                description=description,
                photo_file_id=photo_file_id,
                requested_points=requested_points,
            )
            session.add(evidence)
            session.flush()
            session.expunge(evidence)
            return evidence

    @staticmethod
    def get_evidence(evidence_id: int) -> Optional[Evidence]:
        """Lấy minh chứng theo ID."""
        with get_db_session() as session:
            evidence = session.query(Evidence).filter(
                Evidence.id == evidence_id
            ).first()
            if evidence:
                session.expunge(evidence)
            return evidence

    @staticmethod
    def get_pending_evidences() -> List[Evidence]:
        """Lấy danh sách minh chứng chờ duyệt."""
        with get_db_session() as session:
            evidences = session.query(Evidence).filter(
                Evidence.status == EvidenceStatus.PENDING
            ).order_by(Evidence.created_at.asc()).all()
            
            for e in evidences:
                session.expunge(e)
            return evidences

    @staticmethod
    def get_user_evidences(user_id: int, limit: int = 10) -> List[Evidence]:
        """Lấy minh chứng của user."""
        with get_db_session() as session:
            evidences = session.query(Evidence).filter(
                Evidence.user_id == user_id
            ).order_by(Evidence.created_at.desc()).limit(limit).all()
            
            for e in evidences:
                session.expunge(e)
            return evidences

    @staticmethod
    def approve_evidence(
        evidence_id: int,
        reviewer_id: int,
        reason: str = None
    ) -> bool:
        """
        Duyệt minh chứng và cộng điểm.
        
        Args:
            evidence_id: ID minh chứng
            reviewer_id: ID admin duyệt
            reason: Lý do (optional)
        """
        with get_db_session() as session:
            evidence = session.query(Evidence).filter(
                Evidence.id == evidence_id
            ).first()
            
            if not evidence or evidence.status != EvidenceStatus.PENDING:
                return False
            
            evidence.status = EvidenceStatus.APPROVED
            evidence.reviewed_by = reviewer_id
            evidence.review_reason = reason
            evidence.reviewed_at = datetime.now()
            
            user_id = evidence.user_id
            points = evidence.requested_points
            desc = evidence.description[:50]
            
            session.commit()
        
        # Cộng điểm cho user
        PointService.add_points(
            user_id=user_id,
            points=points,
            reason=f"Minh chứng: {desc}",
            source_type="evidence",
            source_id=evidence_id,
        )
        
        return True

    @staticmethod
    def reject_evidence(
        evidence_id: int,
        reviewer_id: int,
        reason: str
    ) -> bool:
        """
        Từ chối minh chứng.
        
        Args:
            evidence_id: ID minh chứng
            reviewer_id: ID admin duyệt
            reason: Lý do từ chối (bắt buộc)
        """
        with get_db_session() as session:
            evidence = session.query(Evidence).filter(
                Evidence.id == evidence_id
            ).first()
            
            if not evidence or evidence.status != EvidenceStatus.PENDING:
                return False
            
            evidence.status = EvidenceStatus.REJECTED
            evidence.reviewed_by = reviewer_id
            evidence.review_reason = reason
            evidence.reviewed_at = datetime.now()
            session.commit()
            return True

    @staticmethod
    def get_status_display(status: EvidenceStatus) -> str:
        """Hiển thị trạng thái."""
        displays = {
            EvidenceStatus.PENDING: "⏳ Chờ duyệt",
            EvidenceStatus.APPROVED: "✅ Đã duyệt",
            EvidenceStatus.REJECTED: "❌ Từ chối",
        }
        return displays.get(status, "❓ Unknown")

    @staticmethod
    def format_evidence_info(evidence: Evidence, user_name: str = None) -> str:
        """Format thông tin minh chứng."""
        status_display = EvidenceService.get_status_display(evidence.status)
        time_str = evidence.created_at.strftime("%H:%M %d/%m/%Y")
        
        text = (
            f"📋 Minh chứng #{evidence.id}\n"
            f"👤 User: {user_name or evidence.user_id}\n"
            f"📝 Mô tả: {evidence.description}\n"
            f"⭐ Điểm yêu cầu: {evidence.requested_points}\n"
            f"📊 Trạng thái: {status_display}\n"
            f"🕐 Thời gian: {time_str}"
        )
        
        if evidence.review_reason:
            text += f"\n💬 Lý do: {evidence.review_reason}"
        
        return text
