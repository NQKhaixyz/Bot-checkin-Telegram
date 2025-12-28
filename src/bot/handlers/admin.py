"""
Complete admin command handlers.

Consolidates all administrative functions:
- User management (approve, reject, ban, unban)
- User listing
- Location management
- Meeting management
- Evidence approval
- Reporting
- Broadcasting
"""

import logging
from datetime import datetime
from typing import Optional

from telegram import Update, CallbackQuery
from telegram.ext import (
    ContextTypes,
    ConversationHandler,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    filters,
)
from telegram.constants import ParseMode
from telegram.error import BadRequest

from src.services.user_service import UserService
from src.services.geolocation import GeolocationService
from src.services.export import ExportService
from src.services.meeting_service import MeetingService
from src.services.point_service import PointService
from src.services.evidence_service import EvidenceService
from src.database import User, UserStatus, UserRole, MeetingType, MEETING_POINTS
from src.constants import Messages, CallbackData
from src.bot.keyboards import Keyboards
from src.bot.middlewares import require_admin, require_registration, log_action
from src.config import config

logger = logging.getLogger(__name__)


# =============================================================================
# CONVERSATION STATES FOR SET_MEETING
# =============================================================================

(
    MEETING_TITLE,
    MEETING_TIME,
    MEETING_END,
    MEETING_LOCATION,
    MEETING_TYPE,
    MEETING_CONFIRM,
) = range(6)


# =============================================================================
# USER MANAGEMENT COMMANDS
# =============================================================================

@require_registration
@require_admin
@log_action("approve_user")
async def approve_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    user: User = None
) -> None:
    """
    Approve a pending user registration.
    
    Usage: /approve <user_id>
    Example: /approve 123456789
    """
    if not context.args:
        await update.message.reply_text(
            "Su dung: /approve <user_id>\n"
            "Vi du: /approve 123456789\n\n"
            "Dung /list_pending de xem danh sach cho duyet."
        )
        return
    
    try:
        target_id = int(context.args[0])
    except ValueError:
        await update.message.reply_text("ID khong hop le.")
        return
    
    target = UserService.get_user(target_id)
    if not target:
        await update.message.reply_text(f"Khong tim thay user ID: {target_id}")
        return
    
    if target.status != UserStatus.PENDING:
        await update.message.reply_text(
            f"User {target.full_name} khong o trang thai cho duyet."
        )
        return
    
    if UserService.approve_user(target_id, update.effective_user.id):
        await update.message.reply_text(
            f"Da phe duyet: {target.full_name}"
        )
        
        # Notify the user
        try:
            await context.bot.send_message(
                chat_id=target_id,
                text=Messages.REGISTRATION_APPROVED,
                reply_markup=Keyboards.main_menu()
            )
        except Exception as e:
            logger.error(f"Failed to notify user {target_id}: {e}")
    else:
        await update.message.reply_text("Khong the phe duyet user nay.")


@require_registration
@require_admin
@log_action("reject_user")
async def reject_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    user: User = None
) -> None:
    """
    Reject and remove a pending user.
    
    Usage: /reject <user_id>
    """
    if not context.args:
        await update.message.reply_text(
            "Su dung: /reject <user_id>\n"
            "Vi du: /reject 123456789"
        )
        return
    
    try:
        target_id = int(context.args[0])
    except ValueError:
        await update.message.reply_text("ID khong hop le.")
        return
    
    target = UserService.get_user(target_id)
    if not target:
        await update.message.reply_text(f"Khong tim thay user ID: {target_id}")
        return
    
    name = target.full_name
    
    if UserService.reject_user(target_id, update.effective_user.id):
        await update.message.reply_text(f"Da tu choi: {name}")
        
        try:
            await context.bot.send_message(
                chat_id=target_id,
                text=Messages.REGISTRATION_REJECTED
            )
        except Exception:
            pass
    else:
        await update.message.reply_text("Khong the tu choi user nay.")


@require_registration
@require_admin
@log_action("ban_user")
async def ban_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    user: User = None
) -> None:
    """
    Ban an active user.
    
    Usage: /ban <user_id>
    """
    if not context.args:
        await update.message.reply_text(
            "Su dung: /ban <user_id>\n"
            "Vi du: /ban 123456789"
        )
        return
    
    try:
        target_id = int(context.args[0])
    except ValueError:
        await update.message.reply_text("ID khong hop le.")
        return
    
    # Prevent banning super admins
    if config.admin.is_super_admin(target_id):
        await update.message.reply_text("Khong the cam Super Admin!")
        return
    
    target = UserService.get_user(target_id)
    if not target:
        await update.message.reply_text(f"Khong tim thay user ID: {target_id}")
        return
    
    if UserService.ban_user(target_id, update.effective_user.id):
        await update.message.reply_text(f"Da cam: {target.full_name}")
    else:
        await update.message.reply_text("Khong the cam user nay.")


@require_registration
@require_admin
@log_action("unban_user")
async def unban_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    user: User = None
) -> None:
    """
    Unban a banned user.
    
    Usage: /unban <user_id>
    """
    if not context.args:
        await update.message.reply_text(
            "Su dung: /unban <user_id>\n"
            "Vi du: /unban 123456789"
        )
        return
    
    try:
        target_id = int(context.args[0])
    except ValueError:
        await update.message.reply_text("ID khong hop le.")
        return
    
    target = UserService.get_user(target_id)
    if not target:
        await update.message.reply_text(f"Khong tim thay user ID: {target_id}")
        return
    
    if target.status != UserStatus.BANNED:
        await update.message.reply_text(f"User {target.full_name} khong bi cam.")
        return
    
    if UserService.unban_user(target_id, update.effective_user.id):
        await update.message.reply_text(f"Da bo cam: {target.full_name}")
    else:
        await update.message.reply_text("Khong the bo cam user nay.")


# =============================================================================
# USER LISTING COMMANDS
# =============================================================================

@require_registration
@require_admin
async def list_users_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    user: User = None
) -> None:
    """
    List all registered users.
    
    Usage: /list_users
    """
    users = UserService.get_all_users()
    
    if not users:
        await update.message.reply_text("Chua co user nao dang ky.")
        return
    
    # Group by status
    active = [u for u in users if u.status == UserStatus.ACTIVE]
    pending = [u for u in users if u.status == UserStatus.PENDING]
    banned = [u for u in users if u.status == UserStatus.BANNED]
    
    lines = ["DANH SACH NGUOI DUNG\n"]
    
    if active:
        lines.append(f"\nDang hoat dong ({len(active)}):")
        for u in active:
            role = " [Admin]" if u.role == UserRole.ADMIN else ""
            lines.append(f"  - {u.full_name}{role}")
            lines.append(f"    ID: {u.user_id}")
    
    if pending:
        lines.append(f"\nCho duyet ({len(pending)}):")
        for u in pending:
            lines.append(f"  - {u.full_name}")
            lines.append(f"    ID: {u.user_id}")
    
    if banned:
        lines.append(f"\nDa cam ({len(banned)}):")
        for u in banned:
            lines.append(f"  - {u.full_name}")
            lines.append(f"    ID: {u.user_id}")
    
    # Stats summary
    lines.append(f"\n--------------------")
    lines.append(f"Tong: {len(users)} | Active: {len(active)} | Pending: {len(pending)} | Banned: {len(banned)}")
    
    await update.message.reply_text("\n".join(lines))


@require_registration
@require_admin
async def list_pending_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    user: User = None
) -> None:
    """
    List users awaiting approval.
    
    Usage: /list_pending
    """
    pending = UserService.get_pending_users()
    
    if not pending:
        await update.message.reply_text(
            "Khong co user nao dang cho duyet."
        )
        return
    
    await update.message.reply_text(
        f"Co {len(pending)} user dang cho duyet:"
    )
    
    for u in pending:
        await update.message.reply_text(
            f"Ten: {u.full_name}\n"
            f"ID: {u.user_id}\n"
            f"Thoi gian dang ky: {u.joined_at.strftime('%H:%M %d/%m/%Y')}",
            reply_markup=Keyboards.approve_reject_user(u.user_id)
        )


# =============================================================================
# BROADCAST COMMAND
# =============================================================================

@require_registration
@require_admin
@log_action("broadcast")
async def broadcast_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    user: User = None
) -> None:
    """
    Broadcast message to all active users.
    
    Usage: /broadcast <message>
    Example: /broadcast Hom nay hop luc 10h tai phong hop A
    """
    if not context.args:
        await update.message.reply_text(
            "Su dung: /broadcast <tin nhan>\n"
            "Vi du: /broadcast Hom nay hop luc 10h\n\n"
            "Tin nhan se duoc gui den tat ca nhan vien dang hoat dong."
        )
        return
    
    message = " ".join(context.args)
    
    # Get all active users
    active_users = UserService.get_active_users()
    
    if not active_users:
        await update.message.reply_text("Khong co user nao dang hoat dong.")
        return
    
    # Confirm before sending
    await update.message.reply_text(
        f"Se gui tin nhan den {len(active_users)} nguoi:\n\n"
        f"--------------------\n"
        f"{message}\n"
        f"--------------------\n\n"
        f"Dang gui..."
    )
    
    # Send to all users
    success_count = 0
    fail_count = 0
    
    broadcast_message = (
        f"THONG BAO TU ADMIN\n"
        f"--------------------\n\n"
        f"{message}\n\n"
        f"--------------------\n"
        f"{datetime.now().strftime('%H:%M %d/%m/%Y')}"
    )
    
    for target_user in active_users:
        try:
            await context.bot.send_message(
                chat_id=target_user.user_id,
                text=broadcast_message
            )
            success_count += 1
        except Exception as e:
            logger.error(
                f"Failed to send broadcast to {target_user.user_id}: {e}"
            )
            fail_count += 1
    
    await update.message.reply_text(
        f"Da gui thanh cong: {success_count}\n"
        f"Gui that bai: {fail_count}"
    )


# =============================================================================
# LOCATION MANAGEMENT COMMANDS
# =============================================================================

@require_registration
@require_admin
async def list_locations_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    user: User = None
) -> None:
    """
    List all configured office locations.
    
    Usage: /list_locations
    """
    locations = GeolocationService.get_active_locations()
    
    if not locations:
        await update.message.reply_text(
            "Chua co dia diem ACTIVE nao.\n"
            "Su dung /set_location de them dia diem."
        )
        return
    
    lines = ["DANH SACH DIA DIEM (Active)\n"]
    
    for loc in locations:
        coords = GeolocationService.format_coordinates(
            loc.latitude, loc.longitude
        )
        maps_link = GeolocationService.get_google_maps_link(
            loc.latitude, loc.longitude
        )
        
        lines.append(
            f"\n{loc.id}. {loc.name}\n"
            f"   Toa do: {coords}\n"
            f"   Ban kinh: {loc.radius}m\n"
            f"   Maps: {maps_link}"
        )
    
    await update.message.reply_text("\n".join(lines))


@require_registration
@require_admin
@log_action("delete_location")
async def delete_location_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    user: User = None
) -> None:
    """
    Deactivate a location.
    
    Usage: /delete_location <id>
    """
    if not context.args:
        await update.message.reply_text(
            "Su dung: /delete_location <id>\n"
            "Vi du: /delete_location 1\n\n"
            "Dung /list_locations de xem danh sach ID."
        )
        return
    
    try:
        location_id = int(context.args[0])
    except ValueError:
        await update.message.reply_text("ID khong hop le.")
        return
    
    location = GeolocationService.get_location(location_id)
    if not location:
        await update.message.reply_text(f"Khong tim thay dia diem ID: {location_id}")
        return
    
    if GeolocationService.delete_location(location_id):
        await update.message.reply_text(
            f"Da vo hieu hoa dia diem: {location.name}"
        )
    else:
        await update.message.reply_text("Khong the xoa dia diem.")


# =============================================================================
# REPORT COMMANDS
# =============================================================================

@require_registration
@require_admin
@log_action("today_report")
async def today_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    user: User = None
) -> None:
    """
    Show today's attendance summary.
    
    Usage: /today
    """
    report = ExportService.get_daily_report()
    message = ExportService.format_daily_report(report)
    await update.message.reply_text(message)


@require_registration
@require_admin
@log_action("export_excel")
async def export_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    user: User = None
) -> None:
    """
    Export monthly attendance to Excel.
    
    Usage: /export_excel [month] [year]
    """
    from telegram import InputFile
    
    now = datetime.now()
    year = now.year
    month = now.month
    
    if context.args:
        try:
            month = int(context.args[0])
            if not 1 <= month <= 12:
                raise ValueError()
            if len(context.args) > 1:
                year = int(context.args[1])
        except ValueError:
            await update.message.reply_text(
                "Su dung: /export_excel [thang] [nam]\n"
                "Vi du: /export_excel 3 2024"
            )
            return
    
    status = await update.message.reply_text(
        f"Dang tao bao cao thang {month}/{year}..."
    )
    
    try:
        excel_file = ExportService.generate_monthly_excel(year, month)
        filename = f"attendance_{year}_{month:02d}.xlsx"
        
        await update.message.reply_document(
            document=InputFile(excel_file, filename=filename),
            caption=f"Bao cao cham cong thang {month}/{year}"
        )
        
        await status.delete()
        
    except Exception as e:
        logger.error(f"Export failed: {e}")
        await status.edit_text(f"Loi: {str(e)}")


@require_registration
@require_admin
async def stats_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    user: User = None
) -> None:
    """
    Show overall statistics.
    
    Usage: /stats
    """
    user_stats = UserService.get_user_stats()
    today_report = ExportService.get_daily_report()
    now = datetime.now()
    
    stats_text = f"""THONG KE HE THONG

Nhan su:
  - Tong: {user_stats['total']}
  - Hoat dong: {user_stats['active']}
  - Cho duyet: {user_stats['pending']}
  - Da cam: {user_stats['banned']}
  - Admin: {user_stats['admins']}

Hom nay ({now.strftime('%d/%m/%Y')}):
  - Check-in: {today_report.checked_in}/{today_report.total_employees}
  - Dung gio: {today_report.on_time}
  - Muon: {today_report.late}
  - Check-out: {today_report.checked_out}
"""
    
    await update.message.reply_text(stats_text)


# =============================================================================
# MEETING COMMANDS
# =============================================================================

@require_registration
@require_admin
async def list_meetings_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    user: User = None
) -> None:
    """
    List all upcoming meetings.
    
    Usage: /list_meetings
    """
    meetings = MeetingService.get_upcoming_meetings(days=30)
    
    if not meetings:
        await update.message.reply_text(
            "Khong co buoi hop nao sap toi.\n"
            "Su dung /set_meeting de tao buoi hop moi."
        )
        return
    
    lines = ["DANH SACH BUOI HOP\n"]
    
    for meeting in meetings:
        time_str = meeting.meeting_time.strftime("%H:%M %d/%m/%Y")
        end_str = meeting.end_time.strftime("%H:%M %d/%m/%Y") if meeting.end_time else "N/A"
        status = "Active" if meeting.is_active else "Inactive"
        type_display = MeetingService.get_meeting_type_display(meeting.meeting_type)
        lines.append(
            f"\n{meeting.id}. {meeting.title}\n"
            f"   Dia diem: {meeting.location}\n"
            f"   Thoi gian: {time_str} -> {end_str}\n"
            f"   Loai: {type_display}\n"
            f"   Diem: +{meeting.points}\n"
            f"   Trang thai: {status}"
        )
    
    await update.message.reply_text("\n".join(lines))


@require_registration
@require_admin
async def delete_meeting_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    user: User = None
) -> None:
    """
    Delete (deactivate) a meeting and its location.
    
    Usage: /delete_meeting <id>
    """
    if not context.args:
        await update.message.reply_text("Su dung: /delete_meeting <id>")
        return
    
    try:
        meeting_id = int(context.args[0])
    except ValueError:
        await update.message.reply_text("ID khong hop le.")
        return
    
    meeting = MeetingService.get_meeting(meeting_id)
    if not meeting:
        await update.message.reply_text("Khong tim thay buoi hop.")
        return
    
    ok = MeetingService.delete_meeting(meeting_id)
    
    if meeting.location_id:
        GeolocationService.delete_location(meeting.location_id)
    
    if ok:
        await update.message.reply_text(f"Da xoa buoi hop #{meeting_id}. Dia diem da vo hieu hoa.")
    else:
        await update.message.reply_text("Khong the xoa buoi hop.")


async def ranking_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    user: User = None
) -> None:
    """
    Show monthly ranking of all users.
    
    Usage: /ranking
    """
    now = datetime.now()
    
    rankings = PointService.get_all_rankings(month=now.month, year=now.year)
    
    if not rankings:
        await update.message.reply_text(
            "Chua co du lieu xep hang thang nay."
        )
        return
    
    lines = [Messages.RANKING_HEADER.format(month=now.month, year=now.year)]
    
    for ranking in rankings[:20]:  # Top 20
        rank_title = PointService.get_rank_title(ranking.rank)
        lines.append(f"#{ranking.rank} {ranking.user_name} - {rank_title}\n")
    
    await update.message.reply_text("".join(lines))


# =============================================================================
# SET MEETING CONVERSATION HANDLER
# =============================================================================

async def set_meeting_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Start the set_meeting conversation."""
    user_id = update.effective_user.id
    
    # Verify admin
    if not config.admin.is_super_admin(user_id):
        admin = UserService.get_user(user_id)
        if not admin or admin.role != UserRole.ADMIN:
            await update.message.reply_text(Messages.ADMIN_ONLY)
            return ConversationHandler.END
    
    await update.message.reply_text(
        "TAO BUOI HOP MOI\n\n"
        "Nhap TEN buoi hop (VD: Hop thuong ky - Tuan 5)\n\n"
        "Gui /cancel de huy.",
        reply_markup=Keyboards.cancel_only()
    )
    
    return MEETING_TITLE


async def set_meeting_title(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Receive meeting title and ask for time."""
    title = update.message.text.strip()
    
    if not title or title.lower() == "/cancel":
        await update.message.reply_text(
            "Da huy tao buoi hop.",
            reply_markup=Keyboards.admin_menu()
        )
        return ConversationHandler.END
    
    context.user_data["meeting_title"] = title
    
    await update.message.reply_text(
        "Nhap thoi gian hop (HH:MM DD/MM/YYYY)\n"
        "Vi du: 14:00 31/12/2025\n"
        "Gui /cancel de huy.",
        reply_markup=Keyboards.cancel_only()
    )
    
    return MEETING_TIME


async def set_meeting_time(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Receive meeting start time and ask for end time."""
    time_input = update.message.text.strip()
    
    if time_input.lower() == "/cancel":
        await update.message.reply_text(
            "Da huy tao buoi hop.",
            reply_markup=Keyboards.admin_menu()
        )
        return ConversationHandler.END
    
    try:
        meeting_time = datetime.strptime(time_input, "%H:%M %d/%m/%Y")
    except ValueError:
        await update.message.reply_text(
            "Dinh dang khong hop le!\nNhap theo HH:MM DD/MM/YYYY (VD: 14:00 31/12/2025)"
        )
        return MEETING_TIME
    
    if meeting_time <= datetime.now():
        await update.message.reply_text(
            "Thoi gian da qua. Vui long nhap thoi gian trong tuong lai (HH:MM DD/MM/YYYY):"
        )
        return MEETING_TIME
    
    context.user_data["meeting_time"] = meeting_time
    
    await update.message.reply_text(
        "Nhap thoi gian KET THUC hop (HH:MM DD/MM/YYYY):",
        reply_markup=Keyboards.cancel_only()
    )
    return MEETING_END


async def set_meeting_end(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Receive meeting end time and ask for GPS."""
    time_input = update.message.text.strip()
    
    if time_input.lower() == "/cancel":
        await update.message.reply_text(
            "Da huy tao buoi hop.",
            reply_markup=Keyboards.admin_menu()
        )
        return ConversationHandler.END
    
    try:
        end_time = datetime.strptime(time_input, "%H:%M %d/%m/%Y")
    except ValueError:
        await update.message.reply_text(
            "Dinh dang khong hop le!\nNhap theo HH:MM DD/MM/YYYY (VD: 16:00 31/12/2025)"
        )
        return MEETING_END
    
    start_time = context.user_data.get("meeting_time")
    if not start_time or end_time <= start_time:
        await update.message.reply_text(
            "Thoi gian ket thuc phai SAU thoi gian bat dau.\nNhap lai HH:MM DD/MM/YYYY:"
        )
        return MEETING_END
    
    context.user_data["meeting_end"] = end_time
    
    await update.message.reply_text(
        "Gui GPS dia diem hop (bam 'Gui vi tri'):",
        reply_markup=Keyboards.request_location()
    )
    return MEETING_LOCATION


async def set_meeting_location(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Receive GPS location and ask for meeting type."""
    if update.message.location is None:
        await update.message.reply_text(
            "Chua nhan GPS. Bam 'Gui vi tri' de gui GPS:",
            reply_markup=Keyboards.request_location()
        )
        return MEETING_LOCATION
    
    loc = update.message.location
    context.user_data["meeting_lat"] = loc.latitude
    context.user_data["meeting_lon"] = loc.longitude
    context.user_data["meeting_radius"] = config.attendance.geofence_default_radius
    
    await update.message.reply_text(
        "Chon loai buoi hop:\n"
        "  1) Hop thuong (+5)\n"
        "  2) Ho tro dien gia (+10)\n"
        "  3) Hoat dong ngoai khoa (+15)\n"
        "Nhap 1/2/3:",
        reply_markup=Keyboards.cancel_only()
    )
    
    return MEETING_TYPE


async def set_meeting_type(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Receive meeting type and confirm."""
    type_input = update.message.text.strip()
    
    if type_input.lower() == "/cancel":
        await update.message.reply_text(
            "Da huy tao buoi hop.",
            reply_markup=Keyboards.admin_menu()
        )
        return ConversationHandler.END
    
    type_map = {
        "1": MeetingType.REGULAR,
        "2": MeetingType.SUPPORT,
        "3": MeetingType.EVENT,
    }
    
    meeting_type = type_map.get(type_input)
    if not meeting_type:
        await update.message.reply_text("Nhap 1, 2 hoac 3:")
        return MEETING_TYPE
    
    context.user_data["meeting_type"] = meeting_type
    
    # Build confirmation message
    title = context.user_data["meeting_title"]
    meeting_time = context.user_data["meeting_time"]
    meeting_end = context.user_data.get("meeting_end")
    latitude = context.user_data["meeting_lat"]
    longitude = context.user_data["meeting_lon"]
    radius = context.user_data.get("meeting_radius", config.attendance.geofence_default_radius)
    points = MEETING_POINTS.get(meeting_type, 5)
    type_display = MeetingService.get_meeting_type_display(meeting_type)
    time_str = meeting_time.strftime("%H:%M %d/%m/%Y")
    end_str = meeting_end.strftime("%H:%M %d/%m/%Y") if meeting_end else "N/A"
    coords = GeolocationService.format_coordinates(latitude, longitude)
    
    confirmation = (
        "XAC NHAN TAO BUOI HOP\n"
        "====================\n\n"
        f"Tieu de: {title}\n"
        f"Bat dau: {time_str}\n"
        f"Ket thuc: {end_str}\n"
        f"Dia diem: {coords} (ban kinh {radius:.0f}m)\n"
        f"Loai: {type_display}\n"
        f"Diem: +{points}\n\n"
        "Nhap 'ok' de xac nhan hoac /cancel de huy:"
    )
    
    await update.message.reply_text(
        confirmation,
        reply_markup=Keyboards.cancel_only()
    )
    
    return MEETING_CONFIRM


async def set_meeting_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Confirm and create meeting."""
    confirm_input = update.message.text.strip().lower()
    
    if confirm_input == "/cancel" or confirm_input != "ok":
        await update.message.reply_text(
            "Da huy tao buoi hop.",
            reply_markup=Keyboards.admin_menu()
        )
        return ConversationHandler.END
    
    # Create meeting
    title = context.user_data["meeting_title"]
    meeting_type = context.user_data["meeting_type"]
    meeting_time = context.user_data["meeting_time"]
    meeting_end = context.user_data.get("meeting_end")
    latitude = context.user_data.get("meeting_lat")
    longitude = context.user_data.get("meeting_lon")
    radius = context.user_data.get("meeting_radius", config.attendance.geofence_default_radius)
    user_id = update.effective_user.id
    
    location_name = f"Dia diem {title}"
    
    try:
        new_location = GeolocationService.create_location(
            name=location_name,
            latitude=latitude,
            longitude=longitude,
            radius=radius,
            created_by=user_id
        )
        location_id = new_location.id
        
        meeting = MeetingService.create_meeting(
            title=title,
            location=new_location.name,
            meeting_time=meeting_time,
            end_time=meeting_end,
            meeting_type=meeting_type,
            created_by=user_id,
            location_id=location_id,
            latitude=new_location.latitude,
            longitude=new_location.longitude,
            radius=new_location.radius,
        )
        
        meeting_info = MeetingService.format_meeting_info(meeting)
        
        await update.message.reply_text(
            f"DA TAO BUOI HOP THANH CONG!\n\n"
            f"{meeting_info}\n\n"
            f"Su dung /broadcast de gui thong bao den tat ca thanh vien.",
            reply_markup=Keyboards.admin_menu()
        )
        
        logger.info(f"Meeting created: {title} by user {user_id}")
        
    except Exception as e:
        logger.error(f"Failed to create meeting: {e}")
        await update.message.reply_text(
            f"Loi khi tao buoi hop: {str(e)}",
            reply_markup=Keyboards.admin_menu()
        )
    
    # Clean up user data
    context.user_data.pop("meeting_title", None)
    context.user_data.pop("meeting_time", None)
    context.user_data.pop("meeting_end", None)
    context.user_data.pop("meeting_lat", None)
    context.user_data.pop("meeting_lon", None)
    context.user_data.pop("meeting_radius", None)
    context.user_data.pop("meeting_type", None)
    
    return ConversationHandler.END


async def set_meeting_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Cancel the set_meeting conversation."""
    await update.message.reply_text(
        "Da huy tao buoi hop.",
        reply_markup=Keyboards.admin_menu()
    )
    
    # Clean up user data
    context.user_data.pop("meeting_title", None)
    context.user_data.pop("meeting_location", None)
    context.user_data.pop("meeting_location_id", None)
    context.user_data.pop("meeting_lat", None)
    context.user_data.pop("meeting_lon", None)
    context.user_data.pop("meeting_radius", None)
    context.user_data.pop("meeting_type", None)
    context.user_data.pop("meeting_time", None)
    context.user_data.pop("meeting_end", None)
    
    return ConversationHandler.END


# Create the ConversationHandler for set_meeting
set_meeting_handler = ConversationHandler(
    entry_points=[CommandHandler("set_meeting", set_meeting_start)],
    states={
        MEETING_TITLE: [MessageHandler(filters.TEXT & ~filters.COMMAND, set_meeting_title)],
        MEETING_TIME: [MessageHandler(filters.TEXT & ~filters.COMMAND, set_meeting_time)],
        MEETING_END: [MessageHandler(filters.TEXT & ~filters.COMMAND, set_meeting_end)],
        MEETING_LOCATION: [
            MessageHandler(filters.LOCATION, set_meeting_location),
            MessageHandler(filters.TEXT & ~filters.COMMAND, set_meeting_location),
        ],
        MEETING_TYPE: [MessageHandler(filters.TEXT & ~filters.COMMAND, set_meeting_type)],
        MEETING_CONFIRM: [MessageHandler(filters.TEXT & ~filters.COMMAND, set_meeting_confirm)],
    },
    fallbacks=[
        CommandHandler("cancel", set_meeting_cancel),
        MessageHandler(filters.Regex("^Huy$"), set_meeting_cancel),
    ],
    name="set_meeting_conversation",
    persistent=False,
)


# =============================================================================
# HELP COMMAND
# =============================================================================

@require_registration
@require_admin
async def help_admin_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    user: User = None
) -> None:
    """
    Show admin help.
    
    Usage: /help_admin
    """
    help_text = """LENH QUAN TRI

Quan ly User:
  /approve <id> - Duyet user
  /reject <id> - Tu choi user
  /ban <id> - Cam user
  /unban <id> - Bo cam user
  /list_users - Danh sach user
  /list_pending - User cho duyet

Quan ly Buoi hop (gop flow):
  /set_meeting - Tao buoi hop (ten, thoi gian, GPS, chon loai 1/2/3)
  /list_meetings - Danh sach buoi hop
  /delete_meeting <id> - Xoa buoi hop (vo hieu hoa dia diem di kem)

Diem so & Xep hang:
  /ranking - Bang xep hang thang

Bao cao:
  /today - Bao cao hom nay
  /export [thang] [nam] - Xuat Excel
  /stats - Thong ke tong hop

Khac:
  /broadcast <tin> - Gui thong bao
  /help_admin - Tro giup nay
"""
    
    await update.message.reply_text(help_text)


# =============================================================================
# CALLBACK QUERY HANDLER
# =============================================================================

async def admin_callback_handler(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
) -> None:
    """
    Handle inline keyboard callbacks for admin actions.
    """
    query = update.callback_query
    await query.answer()

    async def _edit_query_message(text: str):
        """
        Safely edit the original message (supports photo captions).
        
        Falls back to sending a new message if editing fails.
        """
        try:
            if query.message and (query.message.caption is not None or query.message.photo):
                return await query.edit_message_caption(caption=text)
            return await query.edit_message_text(text)
        except BadRequest as e:
            # Fallback to text edit, ignore "not modified" noise
            if "message is not modified" in str(e).lower():
                return
            try:
                return await query.edit_message_text(text)
            except Exception as inner:
                logger.error(f"Failed to edit callback message: {inner}")
        except Exception as e:
            logger.error(f"Failed to edit callback message: {e}")
        
        # Final fallback: send a new message to the admin
        try:
            await query.message.reply_text(text)
        except Exception:
            pass
    
    user_id = update.effective_user.id
    
    # Verify admin
    if not config.admin.is_super_admin(user_id):
        admin = UserService.get_user(user_id)
        if not admin or admin.role != UserRole.ADMIN:
            await _edit_query_message("Ban khong co quyen.")
            return
    
    data = query.data
    prefix, args = CallbackData.parse(data)
    
    # Handle APPROVE_USER
    if prefix == CallbackData.APPROVE_USER:
        target_id = int(args[0])
        target = UserService.get_user(target_id)
        
        if not target:
            await _edit_query_message("User khong ton tai.")
            return
        
        if UserService.approve_user(target_id, user_id):
            await _edit_query_message(f"Da duyet: {target.full_name}")
            
            try:
                await context.bot.send_message(
                    chat_id=target_id,
                    text=Messages.REGISTRATION_APPROVED,
                    reply_markup=Keyboards.main_menu()
                )
            except Exception:
                pass
        else:
            await _edit_query_message("Khong the duyet user.")
    
    # Handle REJECT_USER
    elif prefix == CallbackData.REJECT_USER:
        target_id = int(args[0])
        target = UserService.get_user(target_id)
        
        if not target:
            await _edit_query_message("User khong ton tai.")
            return
        
        name = target.full_name
        
        if UserService.reject_user(target_id, user_id):
            await _edit_query_message(f"Da tu choi: {name}")
            
            try:
                await context.bot.send_message(
                    chat_id=target_id,
                    text=Messages.REGISTRATION_REJECTED
                )
            except Exception:
                pass
        else:
            await _edit_query_message("Khong the tu choi user.")
    
    # Handle APPROVE_EVIDENCE
    elif prefix == CallbackData.APPROVE_EVIDENCE:
        evidence_id = int(args[0])
        evidence = EvidenceService.get_evidence(evidence_id)
        
        if not evidence:
            await _edit_query_message("Minh chung khong ton tai.")
            return
        
        if EvidenceService.approve_evidence(evidence_id, user_id):
            target_user = UserService.get_user(evidence.user_id)
            user_name = target_user.full_name if target_user else str(evidence.user_id)
            
            await _edit_query_message(
                f"Da duyet minh chung #{evidence_id}\n"
                f"User: {user_name}\n"
                f"Diem: +{evidence.requested_points}"
            )
            
            # Notify the user
            try:
                await context.bot.send_message(
                    chat_id=evidence.user_id,
                    text=Messages.EVIDENCE_APPROVED.format(
                        id=evidence_id,
                        points=evidence.requested_points
                    )
                )
            except Exception as e:
                logger.error(f"Failed to notify user {evidence.user_id}: {e}")
        else:
            await _edit_query_message("Khong the duyet minh chung (co the da duoc xu ly).")
    
    # Handle REJECT_EVIDENCE
    elif prefix == CallbackData.REJECT_EVIDENCE:
        evidence_id = int(args[0])
        evidence = EvidenceService.get_evidence(evidence_id)
        
        if not evidence:
            await _edit_query_message("Minh chung khong ton tai.")
            return
        
        # For rejection, we need a reason - use a default one for inline action
        reason = "Khong du dieu kien hoac thong tin khong chinh xac"
        
        if EvidenceService.reject_evidence(evidence_id, user_id, reason):
            target_user = UserService.get_user(evidence.user_id)
            user_name = target_user.full_name if target_user else str(evidence.user_id)
            
            await _edit_query_message(
                f"Da tu choi minh chung #{evidence_id}\n"
                f"User: {user_name}\n"
                f"Ly do: {reason}"
            )
            
            # Notify the user
            try:
                await context.bot.send_message(
                    chat_id=evidence.user_id,
                    text=Messages.EVIDENCE_REJECTED.format(
                        id=evidence_id,
                        reason=reason
                    )
                )
            except Exception as e:
                logger.error(f"Failed to notify user {evidence.user_id}: {e}")
        else:
            await _edit_query_message("Khong the tu choi minh chung (co the da duoc xu ly).")
    
    # Handle CANCEL
    elif prefix == CallbackData.CANCEL or data == CallbackData.CANCEL:
        await _edit_query_message("Da huy.")
