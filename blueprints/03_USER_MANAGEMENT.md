# User Management Implementation Guide

## Overview

This guide covers the complete user registration flow, approval workflow, and user management features including the `/start` command, registration conversation, and admin approval system.

---

## Prerequisites

- Database models implemented (01_DATABASE_SCHEMA.md)
- Bot core setup completed (02_BOT_CORE.md)

---

## User Flow Diagram

```
                    ┌─────────────┐
                    │   /start    │
                    └──────┬──────┘
                           │
                           ▼
                    ┌─────────────┐
              ┌─────│ User Exists?│─────┐
              │     └─────────────┘     │
              │ No                      │ Yes
              ▼                         ▼
       ┌──────────────┐         ┌─────────────┐
       │ Ask for Name │         │ Show Status │
       └──────┬───────┘         └─────────────┘
              │
              ▼
       ┌──────────────┐
       │ Save as      │
       │ PENDING      │
       └──────┬───────┘
              │
              ▼
       ┌──────────────┐
       │ Notify Admin │
       └──────┬───────┘
              │
              ▼
       ┌──────────────┐
       │ Admin Review │
       └──────┬───────┘
              │
     ┌────────┴────────┐
     │                 │
     ▼                 ▼
┌─────────┐      ┌─────────┐
│ Approve │      │ Reject  │
└────┬────┘      └────┬────┘
     │                │
     ▼                ▼
┌─────────┐      ┌─────────┐
│ ACTIVE  │      │ Removed │
└─────────┘      └─────────┘
```

---

## Implementation Steps

### Step 1: Create User Service

**File: `src/services/user_service.py`**

```python
"""
User management service.

Handles all user-related business logic including registration,
approval, and status management.
"""

import logging
from datetime import datetime
from typing import Optional, List, Tuple

from sqlalchemy.orm import Session
from sqlalchemy import func

from src.database import User, UserStatus, UserRole, get_db_session
from src.config import config

logger = logging.getLogger(__name__)


class UserService:
    """Service class for user management operations."""
    
    @staticmethod
    def get_user(user_id: int) -> Optional[User]:
        """
        Get user by Telegram ID.
        
        Args:
            user_id: Telegram user ID
            
        Returns:
            User object or None if not found
        """
        with get_db_session() as db:
            user = db.query(User).filter(User.user_id == user_id).first()
            if user:
                # Detach from session for use outside context
                db.expunge(user)
            return user
    
    @staticmethod
    def create_user(
        user_id: int, 
        full_name: str,
        role: UserRole = UserRole.MEMBER,
        status: UserStatus = UserStatus.PENDING
    ) -> User:
        """
        Create a new user.
        
        Args:
            user_id: Telegram user ID
            full_name: User's full name
            role: User role (default: MEMBER)
            status: Initial status (default: PENDING)
            
        Returns:
            Created User object
        """
        with get_db_session() as db:
            user = User(
                user_id=user_id,
                full_name=full_name,
                role=role,
                status=status,
                joined_at=datetime.utcnow()
            )
            db.add(user)
            db.flush()
            db.expunge(user)
            logger.info(f"Created user: {user_id} - {full_name}")
            return user
    
    @staticmethod
    def register_user(user_id: int, full_name: str) -> Tuple[User, bool]:
        """
        Register a new user or return existing one.
        
        Args:
            user_id: Telegram user ID
            full_name: User's full name
            
        Returns:
            Tuple of (User, is_new) where is_new indicates if user was created
        """
        existing = UserService.get_user(user_id)
        if existing:
            return existing, False
        
        # Check if user is super admin
        if config.admin.is_super_admin(user_id):
            user = UserService.create_user(
                user_id=user_id,
                full_name=full_name,
                role=UserRole.ADMIN,
                status=UserStatus.ACTIVE  # Auto-approve super admins
            )
        else:
            user = UserService.create_user(
                user_id=user_id,
                full_name=full_name
            )
        
        return user, True
    
    @staticmethod
    def approve_user(user_id: int, approved_by: int = None) -> bool:
        """
        Approve a pending user.
        
        Args:
            user_id: Telegram user ID to approve
            approved_by: Admin user ID who approved
            
        Returns:
            True if approved, False if user not found or not pending
        """
        with get_db_session() as db:
            user = db.query(User).filter(User.user_id == user_id).first()
            
            if not user:
                logger.warning(f"Approve failed: User {user_id} not found")
                return False
            
            if user.status != UserStatus.PENDING:
                logger.warning(
                    f"Approve failed: User {user_id} is not pending "
                    f"(status: {user.status})"
                )
                return False
            
            user.status = UserStatus.ACTIVE
            user.updated_at = datetime.utcnow()
            
            logger.info(
                f"User {user_id} ({user.full_name}) approved by {approved_by}"
            )
            return True
    
    @staticmethod
    def reject_user(user_id: int, rejected_by: int = None) -> bool:
        """
        Reject and remove a pending user.
        
        Args:
            user_id: Telegram user ID to reject
            rejected_by: Admin user ID who rejected
            
        Returns:
            True if rejected, False if user not found
        """
        with get_db_session() as db:
            user = db.query(User).filter(User.user_id == user_id).first()
            
            if not user:
                logger.warning(f"Reject failed: User {user_id} not found")
                return False
            
            full_name = user.full_name
            db.delete(user)
            
            logger.info(
                f"User {user_id} ({full_name}) rejected by {rejected_by}"
            )
            return True
    
    @staticmethod
    def ban_user(user_id: int, banned_by: int = None) -> bool:
        """
        Ban an active user.
        
        Args:
            user_id: Telegram user ID to ban
            banned_by: Admin user ID who banned
            
        Returns:
            True if banned, False if user not found
        """
        with get_db_session() as db:
            user = db.query(User).filter(User.user_id == user_id).first()
            
            if not user:
                logger.warning(f"Ban failed: User {user_id} not found")
                return False
            
            user.status = UserStatus.BANNED
            user.updated_at = datetime.utcnow()
            
            logger.info(
                f"User {user_id} ({user.full_name}) banned by {banned_by}"
            )
            return True
    
    @staticmethod
    def unban_user(user_id: int, unbanned_by: int = None) -> bool:
        """
        Unban a banned user.
        
        Args:
            user_id: Telegram user ID to unban
            unbanned_by: Admin user ID who unbanned
            
        Returns:
            True if unbanned, False if user not found or not banned
        """
        with get_db_session() as db:
            user = db.query(User).filter(User.user_id == user_id).first()
            
            if not user:
                logger.warning(f"Unban failed: User {user_id} not found")
                return False
            
            if user.status != UserStatus.BANNED:
                logger.warning(
                    f"Unban failed: User {user_id} is not banned "
                    f"(status: {user.status})"
                )
                return False
            
            user.status = UserStatus.ACTIVE
            user.updated_at = datetime.utcnow()
            
            logger.info(
                f"User {user_id} ({user.full_name}) unbanned by {unbanned_by}"
            )
            return True
    
    @staticmethod
    def set_admin(user_id: int) -> bool:
        """
        Promote user to admin role.
        
        Args:
            user_id: Telegram user ID to promote
            
        Returns:
            True if promoted, False if user not found
        """
        with get_db_session() as db:
            user = db.query(User).filter(User.user_id == user_id).first()
            
            if not user:
                return False
            
            user.role = UserRole.ADMIN
            user.updated_at = datetime.utcnow()
            
            logger.info(f"User {user_id} promoted to admin")
            return True
    
    @staticmethod
    def get_pending_users() -> List[User]:
        """
        Get all users with PENDING status.
        
        Returns:
            List of pending User objects
        """
        with get_db_session() as db:
            users = db.query(User).filter(
                User.status == UserStatus.PENDING
            ).order_by(User.joined_at.desc()).all()
            
            # Detach from session
            for user in users:
                db.expunge(user)
            
            return users
    
    @staticmethod
    def get_active_users() -> List[User]:
        """
        Get all active users.
        
        Returns:
            List of active User objects
        """
        with get_db_session() as db:
            users = db.query(User).filter(
                User.status == UserStatus.ACTIVE
            ).order_by(User.full_name).all()
            
            for user in users:
                db.expunge(user)
            
            return users
    
    @staticmethod
    def get_all_users() -> List[User]:
        """
        Get all users regardless of status.
        
        Returns:
            List of all User objects
        """
        with get_db_session() as db:
            users = db.query(User).order_by(User.joined_at.desc()).all()
            
            for user in users:
                db.expunge(user)
            
            return users
    
    @staticmethod
    def get_admin_ids() -> List[int]:
        """
        Get all admin user IDs (database + config).
        
        Returns:
            List of admin Telegram user IDs
        """
        admin_ids = set(config.admin.super_admin_ids)
        
        with get_db_session() as db:
            db_admins = db.query(User.user_id).filter(
                User.role == UserRole.ADMIN,
                User.status == UserStatus.ACTIVE
            ).all()
            
            for (user_id,) in db_admins:
                admin_ids.add(user_id)
        
        return list(admin_ids)
    
    @staticmethod
    def get_user_stats() -> dict:
        """
        Get user statistics.
        
        Returns:
            Dictionary with user counts by status
        """
        with get_db_session() as db:
            total = db.query(func.count(User.user_id)).scalar()
            active = db.query(func.count(User.user_id)).filter(
                User.status == UserStatus.ACTIVE
            ).scalar()
            pending = db.query(func.count(User.user_id)).filter(
                User.status == UserStatus.PENDING
            ).scalar()
            banned = db.query(func.count(User.user_id)).filter(
                User.status == UserStatus.BANNED
            ).scalar()
            admins = db.query(func.count(User.user_id)).filter(
                User.role == UserRole.ADMIN
            ).scalar()
            
            return {
                "total": total,
                "active": active,
                "pending": pending,
                "banned": banned,
                "admins": admins
            }
```

### Step 2: Create Start Handler with Registration Conversation

**File: `src/bot/handlers/start.py`**

```python
"""
Start command and registration conversation handler.

Handles the /start command and user registration flow.
"""

import logging
from datetime import datetime

from telegram import Update
from telegram.ext import (
    ContextTypes,
    ConversationHandler,
    CommandHandler,
    MessageHandler,
    filters
)

from src.services.user_service import UserService
from src.database import UserStatus
from src.constants import Messages, KeyboardLabels
from src.bot.keyboards import Keyboards
from src.config import config

logger = logging.getLogger(__name__)

# Conversation states
WAITING_FOR_NAME = 1


async def start_command(
    update: Update, 
    context: ContextTypes.DEFAULT_TYPE
) -> int:
    """
    Handle /start command.
    
    Checks if user exists and either:
    - Shows current status for existing users
    - Starts registration for new users
    
    Returns:
        Conversation state or ConversationHandler.END
    """
    user_id = update.effective_user.id
    telegram_name = update.effective_user.full_name
    
    logger.info(f"Start command from user {user_id} ({telegram_name})")
    
    # Check if user already exists
    existing_user = UserService.get_user(user_id)
    
    if existing_user:
        # User exists, show status
        status_text = {
            UserStatus.ACTIVE: "Da duoc phe duyet",
            UserStatus.PENDING: "Dang cho phe duyet",
            UserStatus.BANNED: "Da bi cam"
        }
        
        await update.message.reply_text(
            Messages.ALREADY_REGISTERED.format(
                status=status_text.get(existing_user.status, existing_user.status)
            ),
            reply_markup=Keyboards.main_menu() if existing_user.status == UserStatus.ACTIVE else None
        )
        return ConversationHandler.END
    
    # New user - ask for name
    await update.message.reply_text(
        Messages.WELCOME,
        reply_markup=Keyboards.remove()
    )
    
    return WAITING_FOR_NAME


async def receive_name(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
) -> int:
    """
    Handle name input during registration.
    
    Validates and saves the user's full name.
    
    Returns:
        ConversationHandler.END
    """
    user_id = update.effective_user.id
    full_name = update.message.text.strip()
    
    # Validate name
    if len(full_name) < 2:
        await update.message.reply_text(
            "Ten qua ngan. Vui long nhap ho ten day du:"
        )
        return WAITING_FOR_NAME
    
    if len(full_name) > 100:
        await update.message.reply_text(
            "Ten qua dai. Vui long nhap ho ten ngan hon:"
        )
        return WAITING_FOR_NAME
    
    # Register user
    user, is_new = UserService.register_user(user_id, full_name)
    
    if not is_new:
        # Shouldn't happen, but handle gracefully
        await update.message.reply_text(
            Messages.ALREADY_REGISTERED.format(status=user.status.value)
        )
        return ConversationHandler.END
    
    # Notify user
    if user.status == UserStatus.ACTIVE:
        # Super admin auto-approved
        await update.message.reply_text(
            f"Chao mung Admin {full_name}!\n"
            "Tai khoan cua ban da duoc kich hoat tu dong.",
            reply_markup=Keyboards.admin_menu()
        )
    else:
        # Regular user needs approval
        await update.message.reply_text(
            Messages.REGISTRATION_PENDING.format(name=full_name)
        )
        
        # Notify admins
        await notify_admins_new_user(context, user_id, full_name)
    
    logger.info(f"User {user_id} registered as '{full_name}'")
    
    return ConversationHandler.END


async def cancel_registration(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
) -> int:
    """Handle registration cancellation."""
    await update.message.reply_text(
        "Dang ky da bi huy. Dung /start de bat dau lai.",
        reply_markup=Keyboards.remove()
    )
    return ConversationHandler.END


async def notify_admins_new_user(
    context: ContextTypes.DEFAULT_TYPE,
    user_id: int,
    full_name: str
) -> None:
    """
    Notify all admins about a new user registration.
    
    Args:
        context: Telegram context
        user_id: New user's Telegram ID
        full_name: New user's name
    """
    admin_ids = UserService.get_admin_ids()
    
    message = Messages.NEW_USER_REQUEST.format(
        user_id=user_id,
        name=full_name,
        time=datetime.now().strftime("%H:%M %d/%m/%Y")
    )
    
    keyboard = Keyboards.approve_reject_user(user_id)
    
    for admin_id in admin_ids:
        try:
            await context.bot.send_message(
                chat_id=admin_id,
                text=message,
                reply_markup=keyboard
            )
        except Exception as e:
            logger.error(f"Failed to notify admin {admin_id}: {e}")


# Registration conversation handler
registration_conversation = ConversationHandler(
    entry_points=[
        CommandHandler("start", start_command)
    ],
    states={
        WAITING_FOR_NAME: [
            MessageHandler(
                filters.TEXT & ~filters.COMMAND,
                receive_name
            )
        ]
    },
    fallbacks=[
        CommandHandler("cancel", cancel_registration),
        MessageHandler(filters.COMMAND, cancel_registration)
    ],
    allow_reentry=True
)
```

### Step 3: Create Admin User Management Handlers

**File: `src/bot/handlers/admin.py`** (partial - user management section)

```python
"""
Admin command handlers.

Handles all administrative operations including user management,
location setup, and reporting.
"""

import logging
from typing import Optional

from telegram import Update, CallbackQuery
from telegram.ext import ContextTypes

from src.services.user_service import UserService
from src.database import User, UserStatus
from src.constants import Messages, CallbackData
from src.bot.keyboards import Keyboards
from src.bot.middlewares import require_admin, log_action
from src.config import config

logger = logging.getLogger(__name__)


# =============================================================================
# USER APPROVAL COMMANDS
# =============================================================================

@require_admin
@log_action("approve_user")
async def approve_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    user: User = None
) -> None:
    """
    Handle /approve <user_id> command.
    
    Approves a pending user registration.
    
    Usage: /approve 123456789
    """
    if not context.args:
        await update.message.reply_text(
            "Su dung: /approve <user_id>\n"
            "Vi du: /approve 123456789"
        )
        return
    
    try:
        target_user_id = int(context.args[0])
    except ValueError:
        await update.message.reply_text(Messages.ERROR_INVALID_INPUT)
        return
    
    target_user = UserService.get_user(target_user_id)
    
    if not target_user:
        await update.message.reply_text(f"Khong tim thay nguoi dung ID: {target_user_id}")
        return
    
    if UserService.approve_user(target_user_id, update.effective_user.id):
        await update.message.reply_text(
            Messages.USER_APPROVED.format(name=target_user.full_name)
        )
        
        # Notify the approved user
        try:
            await context.bot.send_message(
                chat_id=target_user_id,
                text=Messages.REGISTRATION_APPROVED,
                reply_markup=Keyboards.main_menu()
            )
        except Exception as e:
            logger.error(f"Failed to notify user {target_user_id}: {e}")
    else:
        await update.message.reply_text(
            f"Khong the phe duyet nguoi dung {target_user_id}. "
            "Co the da duoc phe duyet hoac khong ton tai."
        )


@require_admin
@log_action("reject_user")
async def reject_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    user: User = None
) -> None:
    """
    Handle /reject <user_id> command.
    
    Rejects and removes a pending user.
    
    Usage: /reject 123456789
    """
    if not context.args:
        await update.message.reply_text(
            "Su dung: /reject <user_id>\n"
            "Vi du: /reject 123456789"
        )
        return
    
    try:
        target_user_id = int(context.args[0])
    except ValueError:
        await update.message.reply_text(Messages.ERROR_INVALID_INPUT)
        return
    
    target_user = UserService.get_user(target_user_id)
    
    if not target_user:
        await update.message.reply_text(f"Khong tim thay nguoi dung ID: {target_user_id}")
        return
    
    user_name = target_user.full_name
    
    if UserService.reject_user(target_user_id, update.effective_user.id):
        await update.message.reply_text(
            Messages.USER_REJECTED.format(name=user_name)
        )
        
        # Notify the rejected user
        try:
            await context.bot.send_message(
                chat_id=target_user_id,
                text=Messages.REGISTRATION_REJECTED
            )
        except Exception as e:
            logger.error(f"Failed to notify user {target_user_id}: {e}")
    else:
        await update.message.reply_text(
            f"Khong the tu choi nguoi dung {target_user_id}."
        )


@require_admin
@log_action("ban_user")
async def ban_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    user: User = None
) -> None:
    """
    Handle /ban <user_id> command.
    
    Bans an active user.
    
    Usage: /ban 123456789
    """
    if not context.args:
        await update.message.reply_text(
            "Su dung: /ban <user_id>\n"
            "Vi du: /ban 123456789"
        )
        return
    
    try:
        target_user_id = int(context.args[0])
    except ValueError:
        await update.message.reply_text(Messages.ERROR_INVALID_INPUT)
        return
    
    # Prevent banning super admins
    if config.admin.is_super_admin(target_user_id):
        await update.message.reply_text("Khong the cam Super Admin!")
        return
    
    target_user = UserService.get_user(target_user_id)
    
    if not target_user:
        await update.message.reply_text(f"Khong tim thay nguoi dung ID: {target_user_id}")
        return
    
    if UserService.ban_user(target_user_id, update.effective_user.id):
        await update.message.reply_text(
            Messages.USER_BANNED.format(name=target_user.full_name)
        )
    else:
        await update.message.reply_text(
            f"Khong the cam nguoi dung {target_user_id}."
        )


@require_admin
@log_action("unban_user")
async def unban_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    user: User = None
) -> None:
    """
    Handle /unban <user_id> command.
    
    Unbans a banned user.
    
    Usage: /unban 123456789
    """
    if not context.args:
        await update.message.reply_text(
            "Su dung: /unban <user_id>\n"
            "Vi du: /unban 123456789"
        )
        return
    
    try:
        target_user_id = int(context.args[0])
    except ValueError:
        await update.message.reply_text(Messages.ERROR_INVALID_INPUT)
        return
    
    target_user = UserService.get_user(target_user_id)
    
    if not target_user:
        await update.message.reply_text(f"Khong tim thay nguoi dung ID: {target_user_id}")
        return
    
    if UserService.unban_user(target_user_id, update.effective_user.id):
        await update.message.reply_text(
            Messages.USER_UNBANNED.format(name=target_user.full_name)
        )
    else:
        await update.message.reply_text(
            f"Khong the bo cam nguoi dung {target_user_id}. "
            "Co the nguoi dung khong bi cam."
        )


# =============================================================================
# USER LISTING COMMANDS
# =============================================================================

@require_admin
async def list_users_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    user: User = None
) -> None:
    """
    Handle /list_users command.
    
    Lists all registered users with their status.
    """
    users = UserService.get_all_users()
    
    if not users:
        await update.message.reply_text("Chua co nguoi dung nao dang ky.")
        return
    
    status_emoji = {
        UserStatus.ACTIVE: "✅",
        UserStatus.PENDING: "⏳",
        UserStatus.BANNED: "🚫"
    }
    
    lines = ["📋 Danh sach nguoi dung:\n"]
    
    for u in users:
        emoji = status_emoji.get(u.status, "❓")
        role_tag = " [Admin]" if u.is_admin else ""
        lines.append(
            f"{emoji} {u.full_name}{role_tag}\n"
            f"   ID: {u.user_id}\n"
            f"   Trang thai: {u.status.value}"
        )
    
    # Add statistics
    stats = UserService.get_user_stats()
    lines.append(
        f"\n📊 Thong ke:\n"
        f"   Tong: {stats['total']}\n"
        f"   Active: {stats['active']}\n"
        f"   Pending: {stats['pending']}\n"
        f"   Banned: {stats['banned']}\n"
        f"   Admins: {stats['admins']}"
    )
    
    await update.message.reply_text("\n".join(lines))


@require_admin
async def list_pending_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    user: User = None
) -> None:
    """
    Handle /list_pending command.
    
    Lists all users awaiting approval.
    """
    pending_users = UserService.get_pending_users()
    
    if not pending_users:
        await update.message.reply_text("Khong co nguoi dung nao dang cho duyet.")
        return
    
    await update.message.reply_text(
        f"⏳ Co {len(pending_users)} nguoi dung dang cho duyet:"
    )
    
    for u in pending_users:
        await update.message.reply_text(
            f"Ten: {u.full_name}\n"
            f"ID: {u.user_id}\n"
            f"Thoi gian dang ky: {u.joined_at.strftime('%H:%M %d/%m/%Y')}",
            reply_markup=Keyboards.approve_reject_user(u.user_id)
        )


# =============================================================================
# CALLBACK QUERY HANDLER
# =============================================================================

async def admin_callback_handler(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
) -> None:
    """
    Handle inline keyboard callbacks for admin actions.
    
    Processes approve/reject button clicks.
    """
    query = update.callback_query
    await query.answer()
    
    user_id = update.effective_user.id
    
    # Verify admin status
    if not config.admin.is_super_admin(user_id):
        admin_user = UserService.get_user(user_id)
        if not admin_user or not admin_user.is_admin:
            await query.edit_message_text("Ban khong co quyen thuc hien hanh dong nay.")
            return
    
    data = query.data
    
    # Handle approve user
    if data.startswith(CallbackData.APPROVE_USER):
        target_id = int(data.split(":")[1])
        target_user = UserService.get_user(target_id)
        
        if not target_user:
            await query.edit_message_text("Nguoi dung khong ton tai.")
            return
        
        if UserService.approve_user(target_id, user_id):
            await query.edit_message_text(
                f"✅ Da phe duyet: {target_user.full_name}"
            )
            
            # Notify approved user
            try:
                await context.bot.send_message(
                    chat_id=target_id,
                    text=Messages.REGISTRATION_APPROVED,
                    reply_markup=Keyboards.main_menu()
                )
            except Exception as e:
                logger.error(f"Failed to notify user {target_id}: {e}")
        else:
            await query.edit_message_text("Khong the phe duyet nguoi dung nay.")
    
    # Handle reject user
    elif data.startswith(CallbackData.REJECT_USER):
        target_id = int(data.split(":")[1])
        target_user = UserService.get_user(target_id)
        
        if not target_user:
            await query.edit_message_text("Nguoi dung khong ton tai.")
            return
        
        user_name = target_user.full_name
        
        if UserService.reject_user(target_id, user_id):
            await query.edit_message_text(
                f"❌ Da tu choi: {user_name}"
            )
            
            # Notify rejected user
            try:
                await context.bot.send_message(
                    chat_id=target_id,
                    text=Messages.REGISTRATION_REJECTED
                )
            except Exception as e:
                logger.error(f"Failed to notify user {target_id}: {e}")
        else:
            await query.edit_message_text("Khong the tu choi nguoi dung nay.")
    
    # Handle cancel
    elif data == CallbackData.CANCEL:
        await query.edit_message_text("Da huy.")
```

---

## Testing User Management

```python
"""Test file: tests/test_user_management.py"""

import pytest
from src.services.user_service import UserService
from src.database import User, UserStatus, UserRole, init_db

@pytest.fixture
def setup_db():
    """Initialize test database."""
    init_db("sqlite:///:memory:")
    yield

def test_register_new_user(setup_db):
    """Test new user registration."""
    user, is_new = UserService.register_user(123, "Test User")
    
    assert is_new == True
    assert user.user_id == 123
    assert user.full_name == "Test User"
    assert user.status == UserStatus.PENDING
    assert user.role == UserRole.MEMBER

def test_register_existing_user(setup_db):
    """Test registration of existing user returns existing."""
    UserService.create_user(456, "Existing User")
    
    user, is_new = UserService.register_user(456, "Different Name")
    
    assert is_new == False
    assert user.full_name == "Existing User"

def test_approve_user(setup_db):
    """Test user approval."""
    UserService.create_user(789, "Pending User")
    
    result = UserService.approve_user(789)
    user = UserService.get_user(789)
    
    assert result == True
    assert user.status == UserStatus.ACTIVE

def test_ban_unban_user(setup_db):
    """Test ban and unban functionality."""
    UserService.create_user(111, "Test", status=UserStatus.ACTIVE)
    
    # Ban user
    UserService.ban_user(111)
    user = UserService.get_user(111)
    assert user.status == UserStatus.BANNED
    
    # Unban user
    UserService.unban_user(111)
    user = UserService.get_user(111)
    assert user.status == UserStatus.ACTIVE
```

---

## Verification Checklist

Before proceeding to the next blueprint, verify:

- [ ] `src/services/user_service.py` created with all methods
- [ ] `src/bot/handlers/start.py` created with registration conversation
- [ ] `src/bot/handlers/admin.py` includes user management commands
- [ ] Registration flow works: `/start` -> Name input -> Pending status
- [ ] Admin approval works: Inline buttons or `/approve <id>`
- [ ] Admin rejection works: Inline buttons or `/reject <id>`
- [ ] Ban/Unban works correctly
- [ ] User listing commands work
- [ ] Notifications sent to users and admins

---

## Next Steps

Proceed to `04_ATTENDANCE_SYSTEM.md` to implement the check-in/check-out system.
