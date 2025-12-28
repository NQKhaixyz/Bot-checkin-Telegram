"""
Check-in and check-out command handlers with location verification and point system.

Uses ConversationHandler for check-in flow with GPS location verification.
"""

import logging
from datetime import datetime

from telegram import Update
from telegram.ext import (
    ContextTypes,
    ConversationHandler,
    CommandHandler,
    MessageHandler,
    filters,
)

from src.services.attendance import AttendanceService
from src.services.meeting_service import MeetingService
from src.services.point_service import PointService
from src.services.user_service import UserService
from src.services.geolocation import GeolocationService
from src.services.anti_cheat import AntiCheatService
from src.database import User
from src.constants import Messages, KeyboardLabels
from src.bot.keyboards import Keyboards
from src.bot.middlewares import require_registration, require_active, log_action

logger = logging.getLogger(__name__)

# Conversation states for checkin
CHECKIN_SELECT_MEETING = 0
CHECKIN_WAITING_FOR_LOCATION = 1


async def _get_user_for_checkin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Helper to get user and validate for checkin. Returns (user, error_sent) tuple."""
    user_id = update.effective_user.id
    user = UserService.get_user(user_id)
    
    if not user:
        await update.message.reply_text(
            "Ban chua dang ky! Dung /start de dang ky.",
            reply_markup=Keyboards.main_menu()
        )
        return None, True
    
    # Handle status as string or enum
    status = user.status.value if hasattr(user.status, 'value') else str(user.status)
    
    if status != "active":
        if status == "pending":
            await update.message.reply_text(
                Messages.REGISTRATION_PENDING,
                reply_markup=Keyboards.main_menu()
            )
        elif status == "banned":
            await update.message.reply_text(
                Messages.ACCOUNT_BANNED,
                reply_markup=Keyboards.main_menu()
            )
        else:
            await update.message.reply_text(
                f"Tai khoan cua ban dang o trang thai: {status}",
                reply_markup=Keyboards.main_menu()
            )
        return None, True
    
    return user, False


async def checkin_start(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> int:
    """Handle /checkin command or 'Diem danh' button - start check-in flow."""
    user, error_sent = await _get_user_for_checkin(update, context)
    if error_sent:
        return ConversationHandler.END
    
    user_id = update.effective_user.id
    
    now = AttendanceService.get_current_time()
    active_meetings = MeetingService.get_active_meetings(now.replace(tzinfo=None))
    
    if not active_meetings:
        await update.message.reply_text(
            Messages.NO_ACTIVE_MEETING,
            reply_markup=Keyboards.main_menu()
        )
        return ConversationHandler.END
    
    # If multiple active meetings, let user pick
    if len(active_meetings) > 1:
        lines = ["Chon buoi hop de diem danh (nhap ID):\n"]
        for m in active_meetings:
            start_str = m.meeting_time.strftime('%H:%M')
            end_str = m.end_time.strftime('%H:%M') if m.end_time else "N/A"
            lines.append(f"{m.id}. {m.title} ({start_str}-{end_str})")
        await update.message.reply_text(
            "\n".join(lines),
            reply_markup=Keyboards.cancel_only()
        )
        context.user_data['checkin_meeting_options'] = {str(m.id): m for m in active_meetings}
        return CHECKIN_SELECT_MEETING
    
    meeting = active_meetings[0]
    
    if AttendanceService.has_checked_in(user_id, meeting.id):
        checkin_log = AttendanceService.get_checkin_log(user_id, meeting.id)
        time_str = checkin_log.timestamp.strftime('%H:%M') if checkin_log else "N/A"
        await update.message.reply_text(
            Messages.CHECKIN_ALREADY.format(time=time_str),
            reply_markup=Keyboards.main_menu()
        )
        return ConversationHandler.END
    
    context.user_data['checkin_meeting_id'] = meeting.id
    context.user_data['checkin_meeting_title'] = meeting.title
    context.user_data['checkin_meeting_location'] = meeting.location
    
    await update.message.reply_text(
        f"DIEM DANH: {meeting.title}\n\n"
        f"Vui long gui vi tri GPS cua ban de xac nhan diem danh.\n"
        f"Bam nut 'Gui vi tri' ben duoi.",
        reply_markup=Keyboards.request_location()
    )
    
    return CHECKIN_WAITING_FOR_LOCATION


async def checkin_location_received(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> int:
    """Handle location message for check-in verification."""
    user_id = update.effective_user.id
    message = update.message
    location = message.location
    
    if not location:
        await update.message.reply_text(
            "Khong nhan duoc vi tri! Vui long gui lai.",
            reply_markup=Keyboards.request_location()
        )
        return CHECKIN_WAITING_FOR_LOCATION
    
    # Get stored meeting info
    meeting_id = context.user_data.get('checkin_meeting_id')
    meeting_title = context.user_data.get('checkin_meeting_title', 'Buoi hop')
    meeting_location = context.user_data.get('checkin_meeting_location', '')
    
    if not meeting_id:
        await update.message.reply_text(
            "Phien diem danh da het han. Vui long thu lai.",
            reply_markup=Keyboards.main_menu()
        )
        return ConversationHandler.END
    
    # Anti-cheat validation
    anti_cheat_result = AntiCheatService.validate_location_message(message)
    
    if not anti_cheat_result.is_valid:
        logger.warning(
            f"Anti-cheat failed for user {user_id}: "
            f"{anti_cheat_result.error_code} - {anti_cheat_result.error_message}"
        )
        await update.message.reply_text(
            f"Loi xac thuc vi tri: {anti_cheat_result.error_message}",
            reply_markup=Keyboards.main_menu()
        )
        # Clear context
        context.user_data.pop('checkin_meeting_id', None)
        context.user_data.pop('checkin_meeting_title', None)
        context.user_data.pop('checkin_meeting_location', None)
        return ConversationHandler.END
    
    # Geolocation validation
    meeting = MeetingService.get_meeting(meeting_id)
    if not meeting:
        await update.message.reply_text(
            "Buoi hop khong ton tai hoac da bi xoa.",
            reply_markup=Keyboards.main_menu()
        )
        context.user_data.pop('checkin_meeting_id', None)
        context.user_data.pop('checkin_meeting_title', None)
        context.user_data.pop('checkin_meeting_location', None)
        return ConversationHandler.END
    
    location_name = meeting_location
    
    now = AttendanceService.get_current_time().replace(tzinfo=None)
    if meeting.meeting_time and meeting.meeting_time > now:
        await update.message.reply_text(
            "Buoi hop chua bat dau. Thu lai khi den gio hop.",
            reply_markup=Keyboards.main_menu()
        )
        return ConversationHandler.END
    if meeting.end_time and meeting.end_time < now:
        await update.message.reply_text(
            "Buoi hop da ket thuc. Khong the check-in.",
            reply_markup=Keyboards.main_menu()
        )
        return ConversationHandler.END
    
    if meeting.latitude is not None and meeting.longitude is not None:
        within_radius, distance = MeetingService.check_location_for_meeting(
            meeting_id,
            location.latitude,
            location.longitude,
        )
        radius = meeting.radius if meeting.radius else 50.0
        
        if not within_radius:
            await update.message.reply_text(
                f"Ban dang o qua xa dia diem hop!\n\n"
                f"Dia diem: {meeting.location}\n"
                f"Khoang cach: {distance:.0f}m\n"
                f"Ban kinh cho phep: {radius:.0f}m\n\n"
                f"Vui long di den dung dia diem va thu lai.",
                reply_markup=Keyboards.main_menu()
            )
            # Clear context
            context.user_data.pop('checkin_meeting_id', None)
            context.user_data.pop('checkin_meeting_title', None)
            context.user_data.pop('checkin_meeting_location', None)
            return ConversationHandler.END
        
        location_name = meeting.location
    else:
        geo_result = GeolocationService.check_location_for_checkin(
            location.latitude,
            location.longitude
        )
        
        if not geo_result.within_radius:
            # Location not within any valid radius
            if geo_result.location:
                distance_str = f"{geo_result.distance_meters:.0f}m"
                await update.message.reply_text(
                    f"Ban dang o qua xa dia diem hop!\n\n"
                    f"Dia diem gan nhat: {geo_result.location.name}\n"
                    f"Khoang cach: {distance_str}\n"
                    f"Ban kinh cho phep: {geo_result.location.radius:.0f}m\n\n"
                    f"Vui long di den dung dia diem va thu lai.",
                    reply_markup=Keyboards.main_menu()
                )
            else:
                await update.message.reply_text(
                    "Khong tim thay dia diem hop nao!\n\n"
                    "Vui long lien he admin de duoc ho tro.",
                    reply_markup=Keyboards.main_menu()
                )
            # Clear context
            context.user_data.pop('checkin_meeting_id', None)
            context.user_data.pop('checkin_meeting_title', None)
            context.user_data.pop('checkin_meeting_location', None)
            return ConversationHandler.END
        
        location_name = geo_result.location.name if geo_result.location else meeting_location
    
    # Location valid - record check-in
    result = AttendanceService.record_checkin(user_id, meeting_id)
    
    # Clear context
    context.user_data.pop('checkin_meeting_id', None)
    context.user_data.pop('checkin_meeting_title', None)
    context.user_data.pop('checkin_meeting_location', None)
    
    if result.success:
        time_str = result.attendance_log.timestamp.strftime('%H:%M')
        await update.message.reply_text(
            Messages.CHECKIN_SUCCESS.format(
                time=time_str,
                meeting=meeting_title,
                location=location_name,
            ),
            reply_markup=Keyboards.main_menu()
        )
        logger.info(
            f"User {user_id} checked in to meeting {meeting_id} "
            f"at location {location_name} ({location.latitude}, {location.longitude})"
        )
    else:
        await update.message.reply_text(
            result.message,
            reply_markup=Keyboards.main_menu()
        )
    
    return ConversationHandler.END


async def checkin_select_meeting(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> int:
    """Handle meeting selection when multiple active meetings."""
    choice = (update.message.text or "").strip()
    options = context.user_data.get('checkin_meeting_options', {})
    meeting = options.get(choice)
    
    if not meeting:
        await update.message.reply_text(
            "ID khong hop le. Nhap lai ID buoi hop:",
            reply_markup=Keyboards.cancel_only()
        )
        return CHECKIN_SELECT_MEETING
    
    user_id = update.effective_user.id
    if AttendanceService.has_checked_in(user_id, meeting.id):
        checkin_log = AttendanceService.get_checkin_log(user_id, meeting.id)
        time_str = checkin_log.timestamp.strftime('%H:%M') if checkin_log else "N/A"
        await update.message.reply_text(
            Messages.CHECKIN_ALREADY.format(time=time_str),
            reply_markup=Keyboards.main_menu()
        )
        return ConversationHandler.END
    
    context.user_data['checkin_meeting_id'] = meeting.id
    context.user_data['checkin_meeting_title'] = meeting.title
    context.user_data['checkin_meeting_location'] = meeting.location
    context.user_data.pop('checkin_meeting_options', None)
    
    await update.message.reply_text(
        f"DIEM DANH: {meeting.title}\n\n"
        f"Gui GPS de xac nhan (bam 'Gui vi tri').",
        reply_markup=Keyboards.request_location()
    )
    
    return CHECKIN_WAITING_FOR_LOCATION


async def checkin_cancel(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> int:
    """Handle cancel during check-in flow."""
    # Clear context
    context.user_data.pop('checkin_meeting_id', None)
    context.user_data.pop('checkin_meeting_title', None)
    context.user_data.pop('checkin_meeting_location', None)
    
    await update.message.reply_text(
        "Da huy diem danh!",
        reply_markup=Keyboards.main_menu()
    )
    return ConversationHandler.END


# Create the conversation handler for check-in
checkin_conversation = ConversationHandler(
    entry_points=[
        CommandHandler("checkin", checkin_start),
        MessageHandler(filters.Regex(f"^{KeyboardLabels.CHECKIN}$"), checkin_start),
    ],
    states={
        CHECKIN_SELECT_MEETING: [
            MessageHandler(filters.TEXT & ~filters.COMMAND, checkin_select_meeting),
            MessageHandler(filters.Regex(f"^{KeyboardLabels.CANCEL}$"), checkin_cancel),
        ],
        CHECKIN_WAITING_FOR_LOCATION: [
            MessageHandler(filters.LOCATION, checkin_location_received),
            MessageHandler(filters.Regex(f"^{KeyboardLabels.CANCEL}$"), checkin_cancel),
        ],
    },
    fallbacks=[
        MessageHandler(filters.Regex(f"^{KeyboardLabels.CANCEL}$"), checkin_cancel),
        CommandHandler("cancel", checkin_cancel),
    ],
    name="checkin_conversation",
    persistent=False,
)


@require_registration
@require_active
@log_action("checkout")
async def checkout_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    user: User = None
) -> None:
    """Handle /checkout command - Check-out va nhan diem (no location verification needed)."""
    user_id = update.effective_user.id
    
    # Get active meeting
    meeting = MeetingService.get_active_meeting()
    
    if not meeting:
        await update.message.reply_text(
            Messages.NO_ACTIVE_MEETING,
            reply_markup=Keyboards.main_menu()
        )
        return
    
    # Check if already checked in
    if not AttendanceService.has_checked_in(user_id, meeting.id):
        await update.message.reply_text(
            Messages.CHECKOUT_NOT_CHECKED_IN,
            reply_markup=Keyboards.main_menu()
        )
        return
    
    # Record checkout
    result = AttendanceService.record_checkout(user_id, meeting.id)
    
    if result.success:
        time_str = result.attendance_log.timestamp.strftime('%H:%M')
        session_minutes = result.attendance_log.duration_minutes or 0
        total_minutes = AttendanceService.get_total_minutes(user_id)
        await update.message.reply_text(
            f"Check-out thanh cong luc {time_str}!\n"
            f"Diem: +{result.points_earned}\n"
            f"Thoi gian hop: {int(session_minutes)} phut\n"
            f"Tong thoi gian hop: {int(total_minutes)} phut",
            reply_markup=Keyboards.main_menu()
        )
    else:
        await update.message.reply_text(
            result.message,
            reply_markup=Keyboards.main_menu()
        )


@require_registration
@require_active
async def status_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    user: User = None
) -> None:
    """
    Handle /status command.
    Gop status + history: Hien thi ten, diem thang, diem ky, rank, muc CC.
    """
    user_id = update.effective_user.id
    user_data = UserService.get_user(user_id)
    
    if not user_data:
        await update.message.reply_text(
            "Chua dang ky! Dung /start de dang ky.",
            reply_markup=Keyboards.main_menu()
        )
        return
    
    # Get points and ranking info
    ranking = PointService.get_user_ranking(user_id)
    
    if ranking:
        monthly_points = ranking.monthly_points
        total_points = ranking.total_points
        rank = ranking.rank
        rank_title = PointService.get_rank_title(rank)
        cc_month = PointService.get_monthly_cc_display(monthly_points)
        cc_term = PointService.get_term_cc_display(ranking.warning_level)
    else:
        monthly_points = 0
        total_points = 0
        rank = "-"
        rank_title = "Chua xep hang"
        cc_month = PointService.get_monthly_cc_display(0)
        cc_term = PointService.get_term_cc_display(user_data.warning_level)
    
    status_text = Messages.STATUS_TEMPLATE.format(
        name=user_data.full_name,
        monthly_points=monthly_points,
        total_points=total_points,
        rank=rank,
        rank_title=rank_title,
        cc_month=cc_month,
        cc_term=cc_term,
    )
    
    await update.message.reply_text(
        status_text,
        reply_markup=Keyboards.main_menu()
    )


async def cancel_action(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
) -> None:
    """Handle cancel button press."""
    await update.message.reply_text(
        "Da huy!",
        reply_markup=Keyboards.main_menu()
    )
