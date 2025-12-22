"""
Help command handler for all users.
"""

from datetime import datetime, timedelta
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from telegram.error import BadRequest

from src.services.user_service import UserService
from src.database import UserRole
from src.config import config


# Store muted users: {user_id: unmute_timestamp}
muted_users = {}

# Mute duration in minutes
MUTE_DURATION = 30


def is_user_muted(user_id: int) -> bool:
    """Check if user is currently muted."""
    if user_id not in muted_users:
        return False
    
    if datetime.now() >= muted_users[user_id]:
        # Mute expired, remove from dict
        del muted_users[user_id]
        return False
    
    return True


def get_mute_remaining(user_id: int) -> int:
    """Get remaining mute time in minutes."""
    if user_id not in muted_users:
        return 0
    
    remaining = muted_users[user_id] - datetime.now()
    return max(0, int(remaining.total_seconds() / 60))


def mute_user(user_id: int) -> None:
    """Mute a user for MUTE_DURATION minutes."""
    muted_users[user_id] = datetime.now() + timedelta(minutes=MUTE_DURATION)


async def check_muted(update: Update) -> bool:
    """Check if user is muted and send message if so. Returns True if muted."""
    user_id = update.effective_user.id
    
    # Super admin bypass
    if config.admin.is_super_admin(user_id):
        return False
    
    if is_user_muted(user_id):
        remaining = get_mute_remaining(user_id)
        await update.message.reply_text(
            f"🔇 Im lặng nào!\n\n"
            f"🚫 Em không có quyền lên tiếng ở đây!\n\n"
            f"🙏 Em có thể đến xin Ngọc Minh...\n\n"
            f"⚠️ Nhưng mà vẫn XÁC ĐỊNH LÀ MUTE!\n\n"
            f"⏰ Còn {remaining} phút nữa! 💀"
        )
        return True
    
    return False


async def help_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
) -> None:
    """
    Show help based on user role.
    
    Usage: /help
    """
    # Check if muted
    if await check_muted(update):
        return
    
    user_id = update.effective_user.id
    user = UserService.get_user(user_id)
    
    # Basic help for all users
    basic_help = """📖 HƯỚNG DẪN - CLB ĐIỂM DANH 🔥

🏃 Điểm danh đi họp:
  • Bấm "📥 Điểm danh" hoặc /checkin
  • Gửi location GPS khi bot yêu cầu
  • Tương tự cho Check-out

📊 Xem thông tin:
  /status - Status hôm nay
  /history - History tháng này

⚠️ LƯU Ý:
  • Phải ở đúng địa điểm họp mới điểm danh được nha!
  • Đừng fake loc, Bot slay lắm! 🕵️💅
  • Location phải gửi trong vòng 60 giây!

🍵 Easter egg:
  /ngocminh - Có giỏi thì bấm đi? 😏

💪 Good luck! Đừng có cúp họp nha! 😏🔥
"""
    
    await update.message.reply_text(basic_help)
    
    # Admin additional help
    if user and user.role == UserRole.ADMIN:
        await update.message.reply_text(
            "👑 Bro là Admin nè! Dùng /help_admin để xem lệnh quản trị nha! 🔥"
        )


async def ngocminh_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
) -> None:
    """
    Easter egg command for Ngọc Minh.
    
    Usage: /ngocminh
    """
    # Check if muted
    if await check_muted(update):
        return
    
    message = """
🍵✨ NGỌC MINH ✨🍵

💚 Cô gái matcha đáng yêu cute phô mai que nhất thế giới! 💚

👑 Vợ yêu của chocomica 💕

⚠️ CẤM LÉNG PHÉNG ⚠️

🤔 Bro nghĩ sao về Matcha Queen?
"""
    
    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("💚 Yêu Ngọc Minh", callback_data="ngocminh_love"),
            InlineKeyboardButton("💔 Ghét Ngọc Minh", callback_data="ngocminh_hate"),
        ]
    ])
    
    await update.message.reply_text(message, reply_markup=keyboard)


async def ngocminh_callback_handler(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
) -> None:
    """Handle ngocminh inline button callbacks."""
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    data = query.data
    
    # Super admin bypass
    is_super = config.admin.is_super_admin(user_id)
    
    if data == "ngocminh_love":
        if is_super:
            response = (
                "💚🍵 MATCHA QUEEN 🍵💚\n\n"
                "😏 Bro là super admin nên được miễn!\n\n"
                "Nhưng mà... dám yêu vợ NQK à? 👀\n"
                "May mà bro có quyền lực! 😤"
            )
        else:
            # Mute user
            mute_user(user_id)
            response = (
                "🚨🚨🚨 ALERT 🚨🚨🚨\n\n"
                "😱 DÁM YÊU VỢ CỦA NQK?\n\n"
                "🔥 XÁC ĐỊNH COOK LUÔN NHÉ! 🔥\n\n"
                "🔇 Bro bị MUTE 30 PHÚT!\n\n"
                "💀 Lần sau biết thân biết phận nha!\n\n"
                "🍵 Matcha Queen chỉ thuộc về chocomica! 💚"
            )
    
    elif data == "ngocminh_hate":
        if is_super:
            response = (
                "💚🍵 MATCHA QUEEN 🍵💚\n\n"
                "😏 Bro là super admin nên được miễn!\n\n"
                "Nhưng mà... dám ghét Matcha Queen?\n"
                "Coi chừng mất chức đó! 😤👀"
            )
        else:
            # Mute user
            mute_user(user_id)
            response = (
                "🚨🚨🚨 KHÔNG THỂ TIN ĐƯỢC 🚨🚨🚨\n\n"
                "😤 Thực sự trên đời có người GHÉT Matcha Queen?\n\n"
                "🤯 KHÔNG THỂ CHẤP NHẬN!\n\n"
                "⚠️ Thế tốt nhất nên ĂN BAN!\n\n"
                "🔇 Bro bị MUTE 30 PHÚT!\n\n"
                "💀 Về suy nghĩ lại đi nha!\n\n"
                "🍵💚 MATCHA QUEEN FOREVER 💚🍵"
            )
    
    else:
        return
    
    try:
        await query.edit_message_text(response)
    except BadRequest as e:
        # Ignore error if message content is the same (user clicked button multiple times)
        if "Message is not modified" not in str(e):
            raise
