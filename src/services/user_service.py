"""
User service for Telegram Attendance Bot.

Provides business logic for user management operations.
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Dict, List, Optional, Tuple

from src.config import get_config
from src.database import User, UserRole, UserStatus, get_db_session

logger = logging.getLogger(__name__)


class UserService:
    """Service class for user management operations."""
    
    @staticmethod
    def get_user(user_id: int) -> Optional[User]:
        """
        Get a user by their Telegram user ID.
        
        Args:
            user_id: The Telegram user ID.
            
        Returns:
            The User object if found, None otherwise.
        """
        with get_db_session() as db:
            user = db.query(User).filter(User.user_id == user_id).first()
            if user:
                db.expunge(user)
            return user
    
    @staticmethod
    def create_user(
        user_id: int,
        full_name: str,
        role: UserRole = UserRole.MEMBER,
        status: UserStatus = UserStatus.PENDING,
    ) -> User:
        """
        Create a new user.
        
        Args:
            user_id: The Telegram user ID.
            full_name: The user's full name.
            role: The user's role (default: MEMBER).
            status: The user's status (default: PENDING).
            
        Returns:
            The created User object.
            
        Raises:
            Exception: If user creation fails.
        """
        with get_db_session() as db:
            user = User(
                user_id=user_id,
                full_name=full_name,
                role=role,
                status=status,
            )
            db.add(user)
            db.flush()
            db.expunge(user)
            logger.info(f"Created user: {user_id} ({full_name}) with role={role}, status={status}")
            return user
    
    @staticmethod
    def register_user(user_id: int, full_name: str) -> Tuple[User, bool]:
        """
        Register a new user or return existing user.
        
        Super admins are automatically approved and given admin role.
        
        Args:
            user_id: The Telegram user ID.
            full_name: The user's full name.
            
        Returns:
            A tuple of (User, is_new) where is_new indicates if user was just created.
        """
        config = get_config()
        is_super_admin = config.admin.is_super_admin(user_id)
        
        with get_db_session() as db:
            existing_user = db.query(User).filter(User.user_id == user_id).first()
            
            if existing_user:
                # Update full_name if changed
                if existing_user.full_name != full_name:
                    existing_user.full_name = full_name
                    db.flush()
                db.expunge(existing_user)
                return existing_user, False
            
            # Create new user
            if is_super_admin:
                # Auto-approve super admins
                user = User(
                    user_id=user_id,
                    full_name=full_name,
                    role=UserRole.ADMIN,
                    status=UserStatus.ACTIVE,
                )
                logger.info(f"Auto-approved super admin: {user_id} ({full_name})")
            else:
                user = User(
                    user_id=user_id,
                    full_name=full_name,
                    role=UserRole.MEMBER,
                    status=UserStatus.PENDING,
                )
                logger.info(f"Created pending user: {user_id} ({full_name})")
            
            db.add(user)
            db.flush()
            db.expunge(user)
            return user, True
    
    @staticmethod
    def approve_user(user_id: int, approved_by: int) -> Optional[User]:
        """
        Approve a pending user.
        
        Args:
            user_id: The Telegram user ID to approve.
            approved_by: The Telegram user ID of the approving admin.
            
        Returns:
            The approved User object if successful, None if user not found.
        """
        with get_db_session() as db:
            user = db.query(User).filter(User.user_id == user_id).first()
            
            if user is None:
                logger.warning(f"Attempted to approve non-existent user: {user_id}")
                return None
            
            user.status = UserStatus.ACTIVE
            user.updated_at = datetime.utcnow()
            db.flush()
            db.expunge(user)
            logger.info(f"User {user_id} approved by {approved_by}")
            return user
    
    @staticmethod
    def reject_user(user_id: int, rejected_by: int) -> bool:
        """
        Reject and delete a pending user.
        
        Args:
            user_id: The Telegram user ID to reject.
            rejected_by: The Telegram user ID of the rejecting admin.
            
        Returns:
            True if user was deleted, False if user not found.
        """
        with get_db_session() as db:
            user = db.query(User).filter(User.user_id == user_id).first()
            
            if user is None:
                logger.warning(f"Attempted to reject non-existent user: {user_id}")
                return False
            
            db.delete(user)
            logger.info(f"User {user_id} rejected and deleted by {rejected_by}")
            return True
    
    @staticmethod
    def ban_user(user_id: int, banned_by: int) -> Optional[User]:
        """
        Ban a user.
        
        Args:
            user_id: The Telegram user ID to ban.
            banned_by: The Telegram user ID of the banning admin.
            
        Returns:
            The banned User object if successful, None if user not found.
        """
        with get_db_session() as db:
            user = db.query(User).filter(User.user_id == user_id).first()
            
            if user is None:
                logger.warning(f"Attempted to ban non-existent user: {user_id}")
                return None
            
            user.status = UserStatus.BANNED
            user.updated_at = datetime.utcnow()
            db.flush()
            db.expunge(user)
            logger.info(f"User {user_id} banned by {banned_by}")
            return user
    
    @staticmethod
    def unban_user(user_id: int, unbanned_by: int) -> Optional[User]:
        """
        Unban a user (set status to active).
        
        Args:
            user_id: The Telegram user ID to unban.
            unbanned_by: The Telegram user ID of the unbanning admin.
            
        Returns:
            The unbanned User object if successful, None if user not found.
        """
        with get_db_session() as db:
            user = db.query(User).filter(User.user_id == user_id).first()
            
            if user is None:
                logger.warning(f"Attempted to unban non-existent user: {user_id}")
                return None
            
            user.status = UserStatus.ACTIVE
            user.updated_at = datetime.utcnow()
            db.flush()
            db.expunge(user)
            logger.info(f"User {user_id} unbanned by {unbanned_by}")
            return user
    
    @staticmethod
    def set_admin(user_id: int) -> Optional[User]:
        """
        Promote a user to admin role.
        
        Args:
            user_id: The Telegram user ID to promote.
            
        Returns:
            The promoted User object if successful, None if user not found.
        """
        with get_db_session() as db:
            user = db.query(User).filter(User.user_id == user_id).first()
            
            if user is None:
                logger.warning(f"Attempted to promote non-existent user: {user_id}")
                return None
            
            user.role = UserRole.ADMIN
            user.updated_at = datetime.utcnow()
            db.flush()
            db.expunge(user)
            logger.info(f"User {user_id} promoted to admin")
            return user
    
    @staticmethod
    def get_pending_users() -> List[User]:
        """
        Get all users with pending status.
        
        Returns:
            List of pending User objects.
        """
        with get_db_session() as db:
            users = db.query(User).filter(User.status == UserStatus.PENDING).all()
            for user in users:
                db.expunge(user)
            return users
    
    @staticmethod
    def get_active_users() -> List[User]:
        """
        Get all users with active status.
        
        Returns:
            List of active User objects.
        """
        with get_db_session() as db:
            users = db.query(User).filter(User.status == UserStatus.ACTIVE).all()
            for user in users:
                db.expunge(user)
            return users
    
    @staticmethod
    def get_all_users() -> List[User]:
        """
        Get all users.
        
        Returns:
            List of all User objects.
        """
        with get_db_session() as db:
            users = db.query(User).all()
            for user in users:
                db.expunge(user)
            return users
    
    @staticmethod
    def get_admin_ids() -> List[int]:
        """
        Get all admin user IDs (from database and config).
        
        Returns:
            List of admin Telegram user IDs.
        """
        config = get_config()
        admin_ids = set(config.admin.super_admin_ids)
        
        with get_db_session() as db:
            db_admins = db.query(User.user_id).filter(User.role == UserRole.ADMIN).all()
            for (admin_id,) in db_admins:
                admin_ids.add(admin_id)
        
        return list(admin_ids)
    
    @staticmethod
    def get_user_stats() -> Dict[str, int]:
        """
        Get user statistics.
        
        Returns:
            Dictionary with user counts by status and role.
        """
        with get_db_session() as db:
            total = db.query(User).count()
            active = db.query(User).filter(User.status == UserStatus.ACTIVE).count()
            pending = db.query(User).filter(User.status == UserStatus.PENDING).count()
            banned = db.query(User).filter(User.status == UserStatus.BANNED).count()
            admins = db.query(User).filter(User.role == UserRole.ADMIN).count()
            members = db.query(User).filter(User.role == UserRole.MEMBER).count()
            
            return {
                "total": total,
                "active": active,
                "pending": pending,
                "banned": banned,
                "admins": admins,
                "members": members,
            }


__all__ = ["UserService"]
