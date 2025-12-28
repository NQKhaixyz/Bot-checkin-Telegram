"""
Evidence handler - Xử lý minh chứng công việc.

ConversationHandler cho phép user gửi ảnh + caption để tạo minh chứng.
"""

import logging
import re
from telegram import Update
from telegram.ext import (
    ContextTypes,
    ConversationHandler,
    CommandHandler,
    MessageHandler,
    filters,
)

from src.database import User, UserRole
from src.services.evidence_service import EvidenceService
from src.services.user_service import UserService
from src.constants import Messages, KeyboardLabels
from src.bot.keyboards import Keyboards
from src.bot.middlewares import require_registration, require_active
from src.config import config

logger = logging.getLogger(__name__)

# Conversation states
WAITING_FOR_PHOTO = 0
WAITING_FOR_TYPE = 1

EVIDENCE_OPTIONS = {
    "1": ("Tham gia hoat dong tai C1-101", 5),
    "2": ("Ho tro dien gia", 10),
    "3": ("Hoat dong ngoai khoa lon", 15),
    "5": ("Tham gia hoat dong tai C1-101", 5),
    "10": ("Ho tro dien gia", 10),
    "15": ("Hoat dong ngoai khoa lon", 15),
    "+5": ("Tham gia hoat dong tai C1-101", 5),
    "+10": ("Ho tro dien gia", 10),
    "+15": ("Hoat dong ngoai khoa lon", 15),
}

@require_registration
@require_active
async def minhchung_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    user: User = None
) -> int:
    """
    Bắt đầu quá trình gửi minh chứng.
    
    Usage: /minhchung
    """
    await update.message.reply_text(
        "GUI MINH CHUNG (2 BUOC)\n\n"
        "Buoc 1: Gui ANH minh chung.\n"
        "Buoc 2: Chon noi dung (1 trong 3 muc):\n"
        "  1) +5: Tham gia hoat dong tai C1-101\n"
        "  2) +10: Ho tro dien gia\n"
        "  3) +15: Hoat dong ngoai khoa lon\n\n"
        "Gui /cancel de huy.",
        reply_markup=Keyboards.cancel_only()
    )
    return WAITING_FOR_PHOTO


async def handle_evidence_photo(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
) -> int:
    """
    Xử lý ảnh minh chứng được gửi.
    
    Yêu cầu: Ảnh + caption với format: [Mô tả] - [Số điểm]
    VD: "Hỗ trợ diễn giả hội thảo AI - 10"
    """
    # Kiểm tra user
    user = UserService.get_user(update.effective_user.id)
    if not user:
        await update.message.reply_text(
            "Ban chua dang ky. Su dung /start de dang ky."
        )
        return ConversationHandler.END
    
    # Lấy ảnh (ảnh chất lượng cao nhất)
    photo = update.message.photo[-1] if update.message.photo else None
    
    if not photo:
        await update.message.reply_text(
            "Vui long gui ANH minh chung (photo).",
            reply_markup=Keyboards.cancel_only()
        )
        return WAITING_FOR_PHOTO
    
    # Lưu file_id để dùng ở bước sau
    context.user_data["evidence_photo_id"] = photo.file_id
    
    await update.message.reply_text(
        "Da nhan anh.\n"
        "Chon noi dung minh chung (tra loi 1/2/3 hoac +5/+10/+15):\n"
        "  1) +5: Tham gia hoat dong tai C1-101\n"
        "  2) +10: Ho tro dien gia\n"
        "  3) +15: Hoat dong ngoai khoa lon",
        reply_markup=Keyboards.cancel_only()
    )
    
    return WAITING_FOR_TYPE


async def handle_evidence_type(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
) -> int:
    """
    Nhan lua chon minh chung va tao record.
    """
    user = UserService.get_user(update.effective_user.id)
    if not user:
        await update.message.reply_text(
            "Ban chua dang ky. Su dung /start de dang ky.",
            reply_markup=Keyboards.main_menu()
        )
        return ConversationHandler.END
    
    photo_file_id = context.user_data.get("evidence_photo_id")
    if not photo_file_id:
        await update.message.reply_text(
            "Chua co anh. Gui /minhchung de bat dau lai."
        )
        return ConversationHandler.END
    
    choice = (update.message.text or "").strip().lower()
    option = EVIDENCE_OPTIONS.get(choice)
    
    if not option:
        await update.message.reply_text(
            "Lua chon khong hop le. Tra loi 1/2/3 hoac +5/+10/+15:"
        )
        return WAITING_FOR_TYPE
    
    description, requested_points = option
    
    # Tạo minh chứng
    evidence = EvidenceService.create_evidence(
        user_id=user.user_id,
        description=description,
        photo_file_id=photo_file_id,
        requested_points=requested_points,
    )
    
    # Clear cached photo
    context.user_data.pop("evidence_photo_id", None)
    
    # Thông báo user
    await update.message.reply_text(
        Messages.EVIDENCE_SUBMITTED.format(
            description=description,
            points=requested_points
        ),
        reply_markup=Keyboards.main_menu()
    )
    
    # Thông báo admin
    await notify_admins_new_evidence(
        context=context,
        evidence=evidence,
        user=user,
        photo_file_id=photo_file_id
    )
    
    logger.info(
        f"Evidence created: #{evidence.id} by {user.full_name} "
        f"({user.user_id}) - {requested_points} points"
    )
    
    return ConversationHandler.END


async def notify_admins_new_evidence(
    context: ContextTypes.DEFAULT_TYPE,
    evidence,
    user: User,
    photo_file_id: str
) -> None:
    """Thông báo admin về minh chứng mới."""
    
    message_text = (
        f"MINH CHUNG MOI CAN DUYET\n"
        f"========================\n\n"
        f"Tu: {user.full_name}\n"
        f"Mo ta: {evidence.description}\n"
        f"Diem yeu cau: {evidence.requested_points}\n"
        f"Thoi gian: {evidence.created_at.strftime('%H:%M %d/%m/%Y')}"
    )
    
    # Gửi cho super admins
    for admin_id in config.admin.super_admin_ids:
        try:
            # Gửi ảnh kèm caption
            await context.bot.send_photo(
                chat_id=admin_id,
                photo=photo_file_id,
                caption=message_text,
                reply_markup=Keyboards.approve_reject_evidence(evidence.id)
            )
        except Exception as e:
            logger.error(f"Failed to notify admin {admin_id}: {e}")
    
    # Gửi cho admin users trong database
    admins = UserService.get_admin_users()
    for admin in admins:
        if admin.user_id not in config.admin.super_admin_ids:
            try:
                await context.bot.send_photo(
                    chat_id=admin.user_id,
                    photo=photo_file_id,
                    caption=message_text,
                    reply_markup=Keyboards.approve_reject_evidence(evidence.id)
                )
            except Exception as e:
                logger.error(f"Failed to notify admin {admin.user_id}: {e}")


async def cancel_evidence(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
) -> int:
    """Hủy quá trình gửi minh chứng."""
    context.user_data.pop("evidence_photo_id", None)
    await update.message.reply_text(
        "Da huy gui minh chung.",
        reply_markup=Keyboards.main_menu()
    )
    return ConversationHandler.END


# ConversationHandler cho evidence
evidence_conversation = ConversationHandler(
    entry_points=[
        CommandHandler("minhchung", minhchung_command),
        MessageHandler(
            filters.Regex(f"^{KeyboardLabels.MINHCHUNG}$"),
            minhchung_command
        ),
    ],
    states={
        WAITING_FOR_PHOTO: [
            MessageHandler(
                filters.PHOTO,
                handle_evidence_photo
            ),
        ],
        WAITING_FOR_TYPE: [
            MessageHandler(
                filters.TEXT & ~filters.COMMAND,
                handle_evidence_type
            ),
        ],
    },
    fallbacks=[
        MessageHandler(
            filters.Regex(f"^{KeyboardLabels.CANCEL}$"),
            cancel_evidence
        ),
        CommandHandler("cancel", cancel_evidence),
    ],
    allow_reentry=True,
)
