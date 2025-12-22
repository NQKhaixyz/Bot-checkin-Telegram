# Bot Core Implementation Guide

## Overview

This guide covers setting up the core Telegram bot structure using `python-telegram-bot` v20+, including configuration management, application factory, and handler registration.

---

## Prerequisites

- Database models implemented (01_DATABASE_SCHEMA.md)
- Python 3.10+
- `python-telegram-bot>=20.0`

---

## Implementation Steps

### Step 1: Create Configuration Management

**File: `src/config.py`**

```python
"""
Configuration management for Telegram Attendance Bot.

Loads settings from environment variables with sensible defaults.
Uses pydantic for validation (optional) or dataclasses.
"""

import os
from dataclasses import dataclass, field
from typing import List
from datetime import time
from pathlib import Path

from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()


@dataclass
class BotConfig:
    """Telegram Bot configuration."""
    token: str = field(default_factory=lambda: os.getenv("TELEGRAM_BOT_TOKEN", ""))
    
    def __post_init__(self):
        if not self.token:
            raise ValueError("TELEGRAM_BOT_TOKEN environment variable is required")


@dataclass
class DatabaseConfig:
    """Database configuration."""
    url: str = field(
        default_factory=lambda: os.getenv("DATABASE_URL", "sqlite:///./attendance.db")
    )
    echo: bool = field(
        default_factory=lambda: os.getenv("DATABASE_ECHO", "false").lower() == "true"
    )


@dataclass  
class AttendanceConfig:
    """Attendance rules configuration."""
    # Work start time (for late detection)
    work_start_hour: int = field(
        default_factory=lambda: int(os.getenv("WORK_START_HOUR", "9"))
    )
    work_start_minute: int = field(
        default_factory=lambda: int(os.getenv("WORK_START_MINUTE", "0"))
    )
    
    # Late threshold in minutes
    late_threshold_minutes: int = field(
        default_factory=lambda: int(os.getenv("LATE_THRESHOLD_MINUTES", "15"))
    )
    
    # Default geofence radius in meters
    default_radius: int = field(
        default_factory=lambda: int(os.getenv("GEOFENCE_DEFAULT_RADIUS", "50"))
    )
    
    # Maximum allowed time difference for location messages (seconds)
    max_location_age_seconds: int = field(
        default_factory=lambda: int(os.getenv("MAX_LOCATION_AGE_SECONDS", "60"))
    )
    
    @property
    def work_start_time(self) -> time:
        """Get work start time as datetime.time object."""
        return time(hour=self.work_start_hour, minute=self.work_start_minute)


@dataclass
class AdminConfig:
    """Admin configuration."""
    # List of Telegram user IDs who are super admins
    super_admin_ids: List[int] = field(default_factory=list)
    
    def __post_init__(self):
        admin_ids_str = os.getenv("ADMIN_USER_IDS", "")
        if admin_ids_str:
            self.super_admin_ids = [
                int(id.strip()) 
                for id in admin_ids_str.split(",") 
                if id.strip().isdigit()
            ]
    
    def is_super_admin(self, user_id: int) -> bool:
        """Check if user is a super admin (from env config)."""
        return user_id in self.super_admin_ids


@dataclass
class TimezoneConfig:
    """Timezone configuration."""
    timezone: str = field(
        default_factory=lambda: os.getenv("TIMEZONE", "Asia/Ho_Chi_Minh")
    )


@dataclass
class Config:
    """Main configuration class combining all configs."""
    bot: BotConfig = field(default_factory=BotConfig)
    database: DatabaseConfig = field(default_factory=DatabaseConfig)
    attendance: AttendanceConfig = field(default_factory=AttendanceConfig)
    admin: AdminConfig = field(default_factory=AdminConfig)
    timezone: TimezoneConfig = field(default_factory=TimezoneConfig)


# Global config instance
config = Config()
```

### Step 2: Create Constants File

**File: `src/constants.py`**

```python
"""
Application constants and message templates.

Centralizes all text messages for easy localization.
"""

# =============================================================================
# BOT COMMANDS
# =============================================================================

class Commands:
    """Bot command constants."""
    START = "start"
    HELP = "help"
    CHECKIN = "checkin"
    CHECKOUT = "checkout"
    STATUS = "status"
    HISTORY = "history"
    
    # Admin commands
    APPROVE = "approve"
    REJECT = "reject"
    BAN = "ban"
    UNBAN = "unban"
    LIST_USERS = "list_users"
    LIST_PENDING = "list_pending"
    SET_LOCATION = "set_location"
    LIST_LOCATIONS = "list_locations"
    TODAY = "today"
    EXPORT = "export_excel"
    BROADCAST = "broadcast"


# =============================================================================
# CALLBACK DATA PREFIXES
# =============================================================================

class CallbackData:
    """Callback data prefixes for inline keyboards."""
    CHECKIN = "checkin"
    CHECKOUT = "checkout"
    APPROVE_USER = "approve_user"
    REJECT_USER = "reject_user"
    CONFIRM_LOCATION = "confirm_loc"
    CANCEL = "cancel"


# =============================================================================
# MESSAGE TEMPLATES (Vietnamese)
# =============================================================================

class Messages:
    """Bot message templates."""
    
    # Welcome & Registration
    WELCOME = (
        "Chao mung ban den voi Bot Diem Danh!\n\n"
        "Vui long nhap ho ten day du cua ban de dang ky:"
    )
    
    REGISTRATION_PENDING = (
        "Cam on {name}!\n\n"
        "Yeu cau dang ky cua ban da duoc gui den Admin.\n"
        "Vui long doi phe duyet truoc khi su dung cac chuc nang."
    )
    
    REGISTRATION_APPROVED = (
        "Chuc mung! Tai khoan cua ban da duoc phe duyet.\n"
        "Ban co the bat dau diem danh ngay bay gio."
    )
    
    REGISTRATION_REJECTED = (
        "Rat tiec, yeu cau dang ky cua ban da bi tu choi.\n"
        "Vui long lien he Admin de biet them chi tiet."
    )
    
    ALREADY_REGISTERED = (
        "Ban da dang ky roi!\n"
        "Trang thai: {status}"
    )
    
    # Check-in/Check-out
    REQUEST_LOCATION = (
        "Vui long gui vi tri hien tai cua ban de diem danh.\n\n"
        "Nhan vao nut ben duoi hoac gui Location tu Telegram."
    )
    
    CHECKIN_SUCCESS = (
        "Check-in thanh cong!\n\n"
        "Thoi gian: {time}\n"
        "Dia diem: {location}\n"
        "Khoang cach: {distance}m"
    )
    
    CHECKIN_SUCCESS_LATE = (
        "Check-in thanh cong (DI MUON)!\n\n"
        "Thoi gian: {time}\n"
        "Dia diem: {location}\n"
        "Khoang cach: {distance}m\n"
        "Muon: {late_minutes} phut"
    )
    
    CHECKIN_FAILED_DISTANCE = (
        "Check-in that bai!\n\n"
        "Ban dang cach van phong {distance}m.\n"
        "Vui long di chuyen lai gan hon (ban kinh cho phep: {radius}m)."
    )
    
    CHECKIN_FAILED_ALREADY = (
        "Ban da check-in hom nay roi!\n\n"
        "Thoi gian: {time}"
    )
    
    CHECKOUT_SUCCESS = (
        "Check-out thanh cong!\n\n"
        "Thoi gian: {time}\n"
        "Tong thoi gian lam viec: {work_hours}"
    )
    
    CHECKOUT_FAILED_NO_CHECKIN = (
        "Ban chua check-in hom nay!\n"
        "Vui long check-in truoc."
    )
    
    # Location messages
    LOCATION_FORWARDED = (
        "Khong the su dung vi tri duoc chuyen tiep!\n"
        "Vui long gui vi tri hien tai truc tiep."
    )
    
    LOCATION_TOO_OLD = (
        "Vi tri da qua cu ({age} giay truoc)!\n"
        "Vui long gui vi tri moi."
    )
    
    NO_LOCATION_CONFIGURED = (
        "Chua co dia diem van phong nao duoc cau hinh.\n"
        "Vui long lien he Admin."
    )
    
    # Status
    STATUS_TEMPLATE = (
        "Trang thai cua ban:\n\n"
        "Ten: {name}\n"
        "Vai tro: {role}\n"
        "Trang thai: {status}\n"
        "Ngay tham gia: {joined_date}"
    )
    
    TODAY_STATUS = (
        "Hom nay ({date}):\n"
        "- Check-in: {checkin_time}\n"
        "- Check-out: {checkout_time}"
    )
    
    # Admin messages
    NEW_USER_REQUEST = (
        "Co thanh vien moi xin gia nhap:\n\n"
        "ID: {user_id}\n"
        "Ten: {name}\n"
        "Thoi gian: {time}"
    )
    
    USER_APPROVED = "Da phe duyet nguoi dung: {name}"
    USER_REJECTED = "Da tu choi nguoi dung: {name}"
    USER_BANNED = "Da cam nguoi dung: {name}"
    USER_UNBANNED = "Da bo cam nguoi dung: {name}"
    
    LOCATION_SET_REQUEST = (
        "Xac nhan dat vi tri van phong tai day?\n\n"
        "Toa do: {lat}, {lon}\n"
        "Vui long nhap ban kinh cho phep (met):"
    )
    
    LOCATION_SET_SUCCESS = (
        "Da thiet lap vi tri van phong:\n\n"
        "Ten: {name}\n"
        "Toa do: {lat}, {lon}\n"
        "Ban kinh: {radius}m"
    )
    
    # Errors
    ERROR_NOT_REGISTERED = "Ban chua dang ky. Vui long dung /start de dang ky."
    ERROR_NOT_APPROVED = "Tai khoan chua duoc phe duyet. Vui long doi Admin duyet."
    ERROR_BANNED = "Tai khoan cua ban da bi cam."
    ERROR_NOT_ADMIN = "Ban khong co quyen thuc hien lenh nay."
    ERROR_GENERIC = "Da xay ra loi. Vui long thu lai sau."
    ERROR_INVALID_INPUT = "Du lieu khong hop le. Vui long thu lai."


# =============================================================================
# KEYBOARD LABELS
# =============================================================================

class KeyboardLabels:
    """Button and keyboard labels."""
    CHECKIN = "Check-in"
    CHECKOUT = "Check-out"
    STATUS = "Trang thai"
    HISTORY = "Lich su"
    SEND_LOCATION = "Gui vi tri"
    CANCEL = "Huy"
    APPROVE = "Phe duyet"
    REJECT = "Tu choi"
    CONFIRM = "Xac nhan"
```

### Step 3: Create Keyboard Utilities

**File: `src/bot/keyboards.py`**

```python
"""
Telegram keyboard builders for the attendance bot.

Provides reusable keyboard components for user interaction.
"""

from telegram import (
    ReplyKeyboardMarkup, 
    KeyboardButton,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    ReplyKeyboardRemove
)

from src.constants import KeyboardLabels, CallbackData


class Keyboards:
    """Keyboard factory class."""
    
    @staticmethod
    def main_menu() -> ReplyKeyboardMarkup:
        """
        Create main menu keyboard for regular users.
        
        Layout:
        [Check-in] [Check-out]
        [Trang thai] [Lich su]
        """
        keyboard = [
            [
                KeyboardButton(KeyboardLabels.CHECKIN),
                KeyboardButton(KeyboardLabels.CHECKOUT)
            ],
            [
                KeyboardButton(KeyboardLabels.STATUS),
                KeyboardButton(KeyboardLabels.HISTORY)
            ]
        ]
        return ReplyKeyboardMarkup(
            keyboard,
            resize_keyboard=True,
            one_time_keyboard=False
        )
    
    @staticmethod
    def request_location() -> ReplyKeyboardMarkup:
        """
        Create keyboard with location request button.
        
        Layout:
        [Gui vi tri (GPS)]
        [Huy]
        """
        keyboard = [
            [
                KeyboardButton(
                    KeyboardLabels.SEND_LOCATION,
                    request_location=True
                )
            ],
            [
                KeyboardButton(KeyboardLabels.CANCEL)
            ]
        ]
        return ReplyKeyboardMarkup(
            keyboard,
            resize_keyboard=True,
            one_time_keyboard=True
        )
    
    @staticmethod
    def admin_menu() -> ReplyKeyboardMarkup:
        """
        Create admin menu keyboard with additional options.
        
        Layout:
        [Check-in] [Check-out]
        [Danh sach] [Bao cao]
        [Trang thai] [Lich su]
        """
        keyboard = [
            [
                KeyboardButton(KeyboardLabels.CHECKIN),
                KeyboardButton(KeyboardLabels.CHECKOUT)
            ],
            [
                KeyboardButton("Danh sach cho duyet"),
                KeyboardButton("Bao cao hom nay")
            ],
            [
                KeyboardButton(KeyboardLabels.STATUS),
                KeyboardButton(KeyboardLabels.HISTORY)
            ]
        ]
        return ReplyKeyboardMarkup(
            keyboard,
            resize_keyboard=True,
            one_time_keyboard=False
        )
    
    @staticmethod
    def approve_reject_user(user_id: int) -> InlineKeyboardMarkup:
        """
        Create inline keyboard for approving/rejecting users.
        
        Args:
            user_id: Telegram user ID to approve/reject
        """
        keyboard = [
            [
                InlineKeyboardButton(
                    KeyboardLabels.APPROVE,
                    callback_data=f"{CallbackData.APPROVE_USER}:{user_id}"
                ),
                InlineKeyboardButton(
                    KeyboardLabels.REJECT,
                    callback_data=f"{CallbackData.REJECT_USER}:{user_id}"
                )
            ]
        ]
        return InlineKeyboardMarkup(keyboard)
    
    @staticmethod
    def confirm_cancel() -> InlineKeyboardMarkup:
        """Create confirm/cancel inline keyboard."""
        keyboard = [
            [
                InlineKeyboardButton(
                    KeyboardLabels.CONFIRM,
                    callback_data=CallbackData.CONFIRM_LOCATION
                ),
                InlineKeyboardButton(
                    KeyboardLabels.CANCEL,
                    callback_data=CallbackData.CANCEL
                )
            ]
        ]
        return InlineKeyboardMarkup(keyboard)
    
    @staticmethod
    def remove() -> ReplyKeyboardRemove:
        """Remove any existing keyboard."""
        return ReplyKeyboardRemove()
```

### Step 4: Create Bot Application Factory

**File: `src/bot/__init__.py`**

```python
"""
Bot package initialization and application factory.

Creates and configures the Telegram bot application.
"""

from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ConversationHandler,
    filters
)

from src.config import config
from src.database import init_db


def create_application() -> Application:
    """
    Create and configure the Telegram bot application.
    
    This is the main application factory that:
    1. Initializes the database
    2. Creates the bot application
    3. Registers all handlers
    4. Configures error handling
    
    Returns:
        Application: Configured telegram bot application
    
    Usage:
        >>> app = create_application()
        >>> app.run_polling()
    """
    # Initialize database
    init_db(config.database.url)
    
    # Create application
    application = (
        Application.builder()
        .token(config.bot.token)
        .build()
    )
    
    # Register handlers (imported here to avoid circular imports)
    _register_handlers(application)
    
    # Register error handler
    _register_error_handler(application)
    
    return application


def _register_handlers(app: Application) -> None:
    """
    Register all message and command handlers.
    
    Handler registration order matters - more specific handlers
    should be registered before generic ones.
    """
    # Import handlers here to avoid circular imports
    from src.bot.handlers.start import (
        start_command,
        registration_conversation
    )
    from src.bot.handlers.checkin import (
        checkin_command,
        checkout_command,
        location_handler
    )
    from src.bot.handlers.admin import (
        approve_command,
        reject_command,
        list_users_command,
        list_pending_command,
        set_location_command,
        today_command,
        export_command,
        broadcast_command,
        admin_callback_handler
    )
    
    # =========================================================================
    # CONVERSATION HANDLERS (must be first)
    # =========================================================================
    
    # Registration conversation (handles /start and name input)
    app.add_handler(registration_conversation)
    
    # =========================================================================
    # COMMAND HANDLERS - User commands
    # =========================================================================
    
    app.add_handler(CommandHandler("checkin", checkin_command))
    app.add_handler(CommandHandler("checkout", checkout_command))
    app.add_handler(CommandHandler("status", status_command))
    app.add_handler(CommandHandler("history", history_command))
    app.add_handler(CommandHandler("help", help_command))
    
    # =========================================================================
    # COMMAND HANDLERS - Admin commands
    # =========================================================================
    
    app.add_handler(CommandHandler("approve", approve_command))
    app.add_handler(CommandHandler("reject", reject_command))
    app.add_handler(CommandHandler("ban", ban_command))
    app.add_handler(CommandHandler("unban", unban_command))
    app.add_handler(CommandHandler("list_users", list_users_command))
    app.add_handler(CommandHandler("list_pending", list_pending_command))
    app.add_handler(CommandHandler("set_location", set_location_command))
    app.add_handler(CommandHandler("list_locations", list_locations_command))
    app.add_handler(CommandHandler("today", today_command))
    app.add_handler(CommandHandler("export_excel", export_command))
    app.add_handler(CommandHandler("broadcast", broadcast_command))
    
    # =========================================================================
    # MESSAGE HANDLERS
    # =========================================================================
    
    # Location handler (for check-in/check-out)
    app.add_handler(MessageHandler(
        filters.LOCATION,
        location_handler
    ))
    
    # Text message handler for menu buttons
    app.add_handler(MessageHandler(
        filters.TEXT & ~filters.COMMAND,
        text_message_handler
    ))
    
    # =========================================================================
    # CALLBACK QUERY HANDLERS
    # =========================================================================
    
    app.add_handler(CallbackQueryHandler(admin_callback_handler))


def _register_error_handler(app: Application) -> None:
    """Register global error handler."""
    from src.bot.handlers.error import error_handler
    app.add_error_handler(error_handler)


# Placeholder handlers (implement in respective files)
async def status_command(update, context):
    """Placeholder for status command."""
    pass

async def history_command(update, context):
    """Placeholder for history command."""
    pass

async def help_command(update, context):
    """Placeholder for help command."""
    pass

async def ban_command(update, context):
    """Placeholder for ban command."""
    pass

async def unban_command(update, context):
    """Placeholder for unban command."""
    pass

async def list_locations_command(update, context):
    """Placeholder for list locations command."""
    pass

async def text_message_handler(update, context):
    """Placeholder for text message handler."""
    pass
```

### Step 5: Create Main Entry Point

**File: `src/main.py`**

```python
"""
Main entry point for Telegram Attendance Bot.

This module initializes and runs the bot application.

Usage:
    python -m src.main
    
    or
    
    python src/main.py
"""

import logging
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.bot import create_application
from src.config import config


def setup_logging() -> None:
    """Configure application logging."""
    logging.basicConfig(
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        level=logging.INFO,
        handlers=[
            logging.StreamHandler(sys.stdout),
            logging.FileHandler('bot.log', encoding='utf-8')
        ]
    )
    
    # Reduce noise from httpx
    logging.getLogger("httpx").setLevel(logging.WARNING)
    
    # Log startup info
    logger = logging.getLogger(__name__)
    logger.info("Starting Telegram Attendance Bot...")
    logger.info(f"Database: {config.database.url}")
    logger.info(f"Timezone: {config.timezone.timezone}")


def main() -> None:
    """
    Main function to run the bot.
    
    Creates the application and starts polling for updates.
    """
    # Setup logging
    setup_logging()
    logger = logging.getLogger(__name__)
    
    try:
        # Create application
        app = create_application()
        
        # Run the bot
        logger.info("Bot is running. Press Ctrl+C to stop.")
        app.run_polling(
            allowed_updates=["message", "callback_query"],
            drop_pending_updates=True
        )
        
    except KeyboardInterrupt:
        logger.info("Bot stopped by user.")
    except Exception as e:
        logger.exception(f"Fatal error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
```

### Step 6: Create Error Handler

**File: `src/bot/handlers/error.py`**

```python
"""
Global error handler for the Telegram bot.

Catches and logs all unhandled exceptions from handlers.
"""

import logging
import html
import traceback

from telegram import Update
from telegram.ext import ContextTypes
from telegram.constants import ParseMode

from src.config import config
from src.constants import Messages

logger = logging.getLogger(__name__)


async def error_handler(
    update: object, 
    context: ContextTypes.DEFAULT_TYPE
) -> None:
    """
    Handle errors that occur during update processing.
    
    Logs the error and optionally notifies admins.
    
    Args:
        update: The update that caused the error
        context: The context containing error info
    """
    # Log the error
    logger.error(
        "Exception while handling an update:",
        exc_info=context.error
    )
    
    # Build error message for admins
    tb_list = traceback.format_exception(
        None, 
        context.error, 
        context.error.__traceback__
    )
    tb_string = "".join(tb_list)
    
    # Truncate if too long
    if len(tb_string) > 4000:
        tb_string = tb_string[:4000] + "..."
    
    # Format update info
    update_str = update.to_dict() if isinstance(update, Update) else str(update)
    
    error_message = (
        f"An exception was raised while handling an update\n\n"
        f"<pre>update = {html.escape(str(update_str)[:1000])}</pre>\n\n"
        f"<pre>{html.escape(tb_string)}</pre>"
    )
    
    # Notify super admins
    for admin_id in config.admin.super_admin_ids:
        try:
            await context.bot.send_message(
                chat_id=admin_id,
                text=error_message,
                parse_mode=ParseMode.HTML
            )
        except Exception as e:
            logger.error(f"Failed to notify admin {admin_id}: {e}")
    
    # Send user-friendly message to the user
    if isinstance(update, Update) and update.effective_message:
        try:
            await update.effective_message.reply_text(
                Messages.ERROR_GENERIC
            )
        except Exception:
            pass  # Ignore if we can't send message
```

### Step 7: Create Middleware/Decorators

**File: `src/bot/middlewares.py`**

```python
"""
Middleware and decorators for handler functions.

Provides authentication, authorization, and validation decorators.
"""

import functools
import logging
from typing import Callable, Any

from telegram import Update
from telegram.ext import ContextTypes

from src.database import get_db_session, User, UserStatus, UserRole
from src.config import config
from src.constants import Messages

logger = logging.getLogger(__name__)


def require_registration(func: Callable) -> Callable:
    """
    Decorator that requires user to be registered.
    
    Checks if user exists in database before allowing handler execution.
    
    Usage:
        @require_registration
        async def my_handler(update, context, user):
            # user is guaranteed to exist
            pass
    """
    @functools.wraps(func)
    async def wrapper(
        update: Update, 
        context: ContextTypes.DEFAULT_TYPE,
        *args, 
        **kwargs
    ) -> Any:
        user_id = update.effective_user.id
        
        with get_db_session() as db:
            user = db.query(User).filter(User.user_id == user_id).first()
            
            if not user:
                await update.effective_message.reply_text(
                    Messages.ERROR_NOT_REGISTERED
                )
                return
            
            # Pass user to handler
            return await func(update, context, user=user, *args, **kwargs)
    
    return wrapper


def require_active(func: Callable) -> Callable:
    """
    Decorator that requires user to be active (approved).
    
    Checks user status and blocks pending/banned users.
    
    Usage:
        @require_active
        async def my_handler(update, context, user):
            # user is guaranteed to be active
            pass
    """
    @functools.wraps(func)
    async def wrapper(
        update: Update,
        context: ContextTypes.DEFAULT_TYPE,
        *args,
        **kwargs
    ) -> Any:
        user_id = update.effective_user.id
        
        with get_db_session() as db:
            user = db.query(User).filter(User.user_id == user_id).first()
            
            if not user:
                await update.effective_message.reply_text(
                    Messages.ERROR_NOT_REGISTERED
                )
                return
            
            if user.status == UserStatus.PENDING:
                await update.effective_message.reply_text(
                    Messages.ERROR_NOT_APPROVED
                )
                return
            
            if user.status == UserStatus.BANNED:
                await update.effective_message.reply_text(
                    Messages.ERROR_BANNED
                )
                return
            
            return await func(update, context, user=user, *args, **kwargs)
    
    return wrapper


def require_admin(func: Callable) -> Callable:
    """
    Decorator that requires user to be an admin.
    
    Checks both database role and super admin config.
    
    Usage:
        @require_admin
        async def admin_handler(update, context, user):
            # user is guaranteed to be admin
            pass
    """
    @functools.wraps(func)
    async def wrapper(
        update: Update,
        context: ContextTypes.DEFAULT_TYPE,
        *args,
        **kwargs
    ) -> Any:
        user_id = update.effective_user.id
        
        # Check super admin config first
        if config.admin.is_super_admin(user_id):
            with get_db_session() as db:
                user = db.query(User).filter(User.user_id == user_id).first()
                return await func(update, context, user=user, *args, **kwargs)
        
        # Check database role
        with get_db_session() as db:
            user = db.query(User).filter(User.user_id == user_id).first()
            
            if not user:
                await update.effective_message.reply_text(
                    Messages.ERROR_NOT_REGISTERED
                )
                return
            
            if user.role != UserRole.ADMIN:
                await update.effective_message.reply_text(
                    Messages.ERROR_NOT_ADMIN
                )
                return
            
            return await func(update, context, user=user, *args, **kwargs)
    
    return wrapper


def log_action(action_name: str) -> Callable:
    """
    Decorator that logs handler actions.
    
    Args:
        action_name: Name of the action for logging
    
    Usage:
        @log_action("check_in")
        async def checkin_handler(update, context):
            pass
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def wrapper(
            update: Update,
            context: ContextTypes.DEFAULT_TYPE,
            *args,
            **kwargs
        ) -> Any:
            user_id = update.effective_user.id
            username = update.effective_user.username or "N/A"
            
            logger.info(
                f"Action: {action_name} | User: {user_id} ({username})"
            )
            
            try:
                result = await func(update, context, *args, **kwargs)
                logger.info(f"Action {action_name} completed for user {user_id}")
                return result
            except Exception as e:
                logger.error(
                    f"Action {action_name} failed for user {user_id}: {e}"
                )
                raise
        
        return wrapper
    return decorator
```

---

## Environment File Template

**File: `.env.example`**

```env
# =============================================================================
# Telegram Bot Configuration
# =============================================================================
TELEGRAM_BOT_TOKEN=your_bot_token_here

# Comma-separated list of Telegram user IDs who are super admins
ADMIN_USER_IDS=123456789,987654321

# =============================================================================
# Database Configuration
# =============================================================================
# SQLite (default, for small scale)
DATABASE_URL=sqlite:///./attendance.db

# PostgreSQL (for larger scale)
# DATABASE_URL=postgresql://user:password@localhost:5432/attendance

# Set to true to log all SQL queries (debugging)
DATABASE_ECHO=false

# =============================================================================
# Timezone Configuration
# =============================================================================
TIMEZONE=Asia/Ho_Chi_Minh

# =============================================================================
# Attendance Rules
# =============================================================================
# Work start time (24-hour format)
WORK_START_HOUR=9
WORK_START_MINUTE=0

# Minutes after work start time to be considered late
LATE_THRESHOLD_MINUTES=15

# Default geofence radius in meters
GEOFENCE_DEFAULT_RADIUS=50

# Maximum age of location message in seconds (anti-cheat)
MAX_LOCATION_AGE_SECONDS=60
```

---

## Requirements File

**File: `requirements.txt`**

```txt
# Core dependencies
python-telegram-bot>=20.7
sqlalchemy>=2.0.23
python-dotenv>=1.0.0
pytz>=2023.3

# Geolocation
geopy>=2.4.1

# Excel export
openpyxl>=3.1.2

# Database drivers (choose one)
# SQLite is built-in, no extra package needed
# For PostgreSQL:
# psycopg2-binary>=2.9.9

# Optional: Google Sheets integration
# gspread>=5.12.0
# oauth2client>=4.1.3

# Development dependencies
# pytest>=7.4.3
# pytest-asyncio>=0.21.1
```

---

## Verification Checklist

Before proceeding to the next blueprint, verify:

- [ ] `src/config.py` created and loads environment variables
- [ ] `src/constants.py` created with all message templates
- [ ] `src/bot/keyboards.py` created with keyboard builders
- [ ] `src/bot/__init__.py` created with application factory
- [ ] `src/main.py` created as entry point
- [ ] `src/bot/handlers/error.py` created
- [ ] `src/bot/middlewares.py` created with decorators
- [ ] `.env.example` created
- [ ] `requirements.txt` created
- [ ] Bot starts without errors (even if handlers are placeholders)

---

## Next Steps

Proceed to `03_USER_MANAGEMENT.md` to implement user registration and management.
