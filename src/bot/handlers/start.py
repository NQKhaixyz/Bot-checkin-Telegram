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
            UserStatus.ACTIVE: "✅ Đã được duyệt",
            UserStatus.PENDING: "⏳ Đang chờ duyệt",
            UserStatus.BANNED: "🚫 Đã bị ban"
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
        "🎉 Yo yo yo! Welcome to CLB Điểm Danh nha bestie!\n\n"
        "📝 QUAN TRỌNG NÈ:\n"
        "Nhập ĐẦY ĐỦ HỌ TÊN + MSSV của bro nha!\n\n"
        "📌 Ví dụ: Nguyễn Văn A - 22520001\n\n"
        "⚠️ Ghi sai là Admin không duyệt đâu á! Real talk! 💀\n\n"
        "✍️ Nhập đi bro:",
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
            "😅 Ê bro, tên ngắn quá! Nhập đầy đủ họ tên đi nha:"
        )
        return WAITING_FOR_NAME
    
    if len(full_name) > 100:
        await update.message.reply_text(
            "😱 Dài quá bro ơi! Tên gì mà dài như tiểu thuyết vậy? Ngắn lại đi:"
        )
        return WAITING_FOR_NAME
    
    # Register user
    user, is_new = UserService.register_user(user_id, full_name)
    
    if not is_new:
        # Shouldn't happen, but handle gracefully
        user_status = user.status.value if hasattr(user.status, 'value') else str(user.status)
        await update.message.reply_text(
            Messages.ALREADY_REGISTERED.format(status=user_status)
        )
        return ConversationHandler.END
    
    # Notify user
    if user.status == UserStatus.ACTIVE:
        # Super admin auto-approved
        await update.message.reply_text(
            f"👑 Yo Admin {full_name}!\n\n"
            "🔥 Acc được auto-approve vì bro là big boss! Let's go! 💪",
            reply_markup=Keyboards.admin_menu()
        )
    else:
        # Regular user needs approval
        await update.message.reply_text(
            f"✅ Nice! Đã gửi yêu cầu tham gia CLB rồi nha {full_name}!\n\n"
            "⏳ Đợi Admin duyệt xíu nha bestie! Chill đi! 🧋",
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
        "❌ Đã hủy đăng ký! Nhát quá bro ơi! 😏\n\n"
        "👆 Dùng /start để thử lại nha!",
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
