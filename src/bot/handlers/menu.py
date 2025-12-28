"""
Menu button handler for text messages.

Routes text messages from reply keyboard buttons to appropriate handlers.
"""

from telegram import Update
from telegram.ext import ContextTypes

from src.constants import KeyboardLabels
from src.bot.handlers.checkin import (
    checkout_command,
    status_command,
    cancel_action
)
from src.bot.handlers.evidence import minhchung_command


async def text_message_handler(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
) -> None:
    """
    Handle text messages from reply keyboard buttons.
    
    Routes button presses to appropriate handlers.
    """
    text = update.message.text
    
    # User menu handlers
    # Note: KeyboardLabels.CHECKIN ("Diem danh") is handled by checkin_conversation
    user_handlers = {
        KeyboardLabels.CHECKOUT: checkout_command,
        "📤 Check-out": checkout_command,
        KeyboardLabels.STATUS: status_command,
        "📊 Trạng thái": status_command,
        KeyboardLabels.MINHCHUNG: minhchung_command,
        KeyboardLabels.CANCEL: cancel_action,
        "❌ Hủy": cancel_action,
    }
    
    handler = user_handlers.get(text)
    
    if handler:
        await handler(update, context)
        return
    
    # Admin menu handlers - import lazily to avoid circular imports
    from src.bot.handlers.admin import (
        list_pending_command,
        list_users_command,
        today_command,
        export_command,
        broadcast_command,
        list_meetings_command,
        ranking_command,
    )
    
    admin_handlers = {
        KeyboardLabels.LIST_PENDING: list_pending_command,
        "⏳ Chờ duyệt": list_pending_command,
        KeyboardLabels.LIST_USERS: list_users_command,
        "👥 DS Người dùng": list_users_command,
        KeyboardLabels.TODAY_REPORT: today_command,
        "📊 Báo cáo hôm nay": today_command,
        KeyboardLabels.EXPORT: export_command,
        "📁 Xuất báo cáo": export_command,
        KeyboardLabels.MEETINGS: list_meetings_command,
        KeyboardLabels.RANKING: ranking_command,
        KeyboardLabels.BROADCAST: broadcast_command,
        "📢 Thông báo": broadcast_command,
    }
    
    admin_handler = admin_handlers.get(text)
    
    if admin_handler:
        await admin_handler(update, context)
        return
    
    # Unknown text - ignore (might be conversation input)
    pass
