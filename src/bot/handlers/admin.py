"""
Complete admin command handlers.

Consolidates all administrative functions:
- User management (approve, reject, ban, unban)
- User listing
- Location management
- Reporting
- Broadcasting
"""

import logging
from datetime import datetime
from typing import Optional

from telegram import Update, CallbackQuery
from telegram.ext import ContextTypes
from telegram.constants import ParseMode

from src.services.user_service import UserService
from src.services.geolocation import GeolocationService
from src.services.export import ExportService
from src.database import User, UserStatus, UserRole
from src.constants import Messages, CallbackData
from src.bot.keyboards import Keyboards
from src.bot.middlewares import require_admin, require_registration, log_action
from src.config import config

logger = logging.getLogger(__name__)


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
    locations = GeolocationService.get_all_locations()
    
    if not locations:
        await update.message.reply_text(
            "Chua co dia diem nao duoc cau hinh.\n"
            "Su dung /set_location de them dia diem."
        )
        return
    
    lines = ["DANH SACH DIA DIEM\n"]
    
    for loc in locations:
        status = "Active" if loc.is_active else "Inactive"
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
            f"   Trang thai: {status}\n"
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

Quan ly Dia diem:
  /set_location - Them dia diem moi
  /list_locations - Danh sach dia diem
  /delete_location <id> - Xoa dia diem

Bao cao:
  /today - Bao cao hom nay
  /export_excel [thang] [nam] - Xuat Excel
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
    
    user_id = update.effective_user.id
    
    # Verify admin
    if not config.admin.is_super_admin(user_id):
        admin = UserService.get_user(user_id)
        if not admin or admin.role != UserRole.ADMIN:
            await query.edit_message_text("Ban khong co quyen.")
            return
    
    data = query.data
    
    if data.startswith(CallbackData.APPROVE_USER):
        target_id = int(data.split(":")[1])
        target = UserService.get_user(target_id)
        
        if not target:
            await query.edit_message_text("User khong ton tai.")
            return
        
        if UserService.approve_user(target_id, user_id):
            await query.edit_message_text(f"Da duyet: {target.full_name}")
            
            try:
                await context.bot.send_message(
                    chat_id=target_id,
                    text=Messages.REGISTRATION_APPROVED,
                    reply_markup=Keyboards.main_menu()
                )
            except Exception:
                pass
        else:
            await query.edit_message_text("Khong the duyet user.")
    
    elif data.startswith(CallbackData.REJECT_USER):
        target_id = int(data.split(":")[1])
        target = UserService.get_user(target_id)
        
        if not target:
            await query.edit_message_text("User khong ton tai.")
            return
        
        name = target.full_name
        
        if UserService.reject_user(target_id, user_id):
            await query.edit_message_text(f"Da tu choi: {name}")
            
            try:
                await context.bot.send_message(
                    chat_id=target_id,
                    text=Messages.REGISTRATION_REJECTED
                )
            except Exception:
                pass
        else:
            await query.edit_message_text("Khong the tu choi user.")
    
    elif data == CallbackData.CANCEL:
        await query.edit_message_text("Da huy.")
