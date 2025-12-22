# Admin Commands Reference Guide

## Overview

This guide provides a complete reference for all admin commands, including the broadcast feature and help system. It consolidates all admin functionality from previous blueprints.

---

## Command Summary Table

| Command | Description | Usage |
|---------|-------------|-------|
| `/approve` | Approve pending user | `/approve <user_id>` |
| `/reject` | Reject pending user | `/reject <user_id>` |
| `/ban` | Ban active user | `/ban <user_id>` |
| `/unban` | Unban banned user | `/unban <user_id>` |
| `/list_users` | List all users | `/list_users` |
| `/list_pending` | List pending users | `/list_pending` |
| `/set_location` | Add office location | `/set_location` (interactive) |
| `/list_locations` | List all locations | `/list_locations` |
| `/delete_location` | Remove location | `/delete_location <id>` |
| `/today` | Today's attendance | `/today` |
| `/export_excel` | Export monthly report | `/export_excel [month] [year]` |
| `/broadcast` | Send to all users | `/broadcast <message>` |
| `/stats` | Show statistics | `/stats` |
| `/help_admin` | Admin help | `/help_admin` |

---

## Complete Admin Handler Implementation

**File: `src/bot/handlers/admin.py`**

```python
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
from src.bot.middlewares import require_admin, log_action
from src.config import config

logger = logging.getLogger(__name__)


# =============================================================================
# USER MANAGEMENT COMMANDS
# =============================================================================

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
            "Sử dụng: /approve <user_id>\n"
            "Ví dụ: /approve 123456789\n\n"
            "Dùng /list_pending để xem danh sách chờ duyệt."
        )
        return
    
    try:
        target_id = int(context.args[0])
    except ValueError:
        await update.message.reply_text("ID không hợp lệ.")
        return
    
    target = UserService.get_user(target_id)
    if not target:
        await update.message.reply_text(f"Không tìm thấy user ID: {target_id}")
        return
    
    if target.status != UserStatus.PENDING:
        await update.message.reply_text(
            f"User {target.full_name} không ở trạng thái chờ duyệt."
        )
        return
    
    if UserService.approve_user(target_id, update.effective_user.id):
        await update.message.reply_text(
            f"✅ Đã phê duyệt: {target.full_name}"
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
        await update.message.reply_text("Không thể phê duyệt user này.")


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
            "Sử dụng: /reject <user_id>\n"
            "Ví dụ: /reject 123456789"
        )
        return
    
    try:
        target_id = int(context.args[0])
    except ValueError:
        await update.message.reply_text("ID không hợp lệ.")
        return
    
    target = UserService.get_user(target_id)
    if not target:
        await update.message.reply_text(f"Không tìm thấy user ID: {target_id}")
        return
    
    name = target.full_name
    
    if UserService.reject_user(target_id, update.effective_user.id):
        await update.message.reply_text(f"❌ Đã từ chối: {name}")
        
        try:
            await context.bot.send_message(
                chat_id=target_id,
                text=Messages.REGISTRATION_REJECTED
            )
        except Exception:
            pass
    else:
        await update.message.reply_text("Không thể từ chối user này.")


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
            "Sử dụng: /ban <user_id>\n"
            "Ví dụ: /ban 123456789"
        )
        return
    
    try:
        target_id = int(context.args[0])
    except ValueError:
        await update.message.reply_text("ID không hợp lệ.")
        return
    
    # Prevent banning super admins
    if config.admin.is_super_admin(target_id):
        await update.message.reply_text("⚠️ Không thể cấm Super Admin!")
        return
    
    target = UserService.get_user(target_id)
    if not target:
        await update.message.reply_text(f"Không tìm thấy user ID: {target_id}")
        return
    
    if UserService.ban_user(target_id, update.effective_user.id):
        await update.message.reply_text(f"🚫 Đã cấm: {target.full_name}")
    else:
        await update.message.reply_text("Không thể cấm user này.")


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
            "Sử dụng: /unban <user_id>\n"
            "Ví dụ: /unban 123456789"
        )
        return
    
    try:
        target_id = int(context.args[0])
    except ValueError:
        await update.message.reply_text("ID không hợp lệ.")
        return
    
    target = UserService.get_user(target_id)
    if not target:
        await update.message.reply_text(f"Không tìm thấy user ID: {target_id}")
        return
    
    if target.status != UserStatus.BANNED:
        await update.message.reply_text(f"User {target.full_name} không bị cấm.")
        return
    
    if UserService.unban_user(target_id, update.effective_user.id):
        await update.message.reply_text(f"✅ Đã bỏ cấm: {target.full_name}")
    else:
        await update.message.reply_text("Không thể bỏ cấm user này.")


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
    List all registered users.
    
    Usage: /list_users
    """
    users = UserService.get_all_users()
    
    if not users:
        await update.message.reply_text("Chưa có user nào đăng ký.")
        return
    
    # Group by status
    active = [u for u in users if u.status == UserStatus.ACTIVE]
    pending = [u for u in users if u.status == UserStatus.PENDING]
    banned = [u for u in users if u.status == UserStatus.BANNED]
    
    lines = ["📋 DANH SÁCH NGƯỜI DÙNG\n"]
    
    if active:
        lines.append(f"\n✅ Đang hoạt động ({len(active)}):")
        for u in active:
            role = " [Admin]" if u.role == UserRole.ADMIN else ""
            lines.append(f"  • {u.full_name}{role}")
            lines.append(f"    ID: {u.user_id}")
    
    if pending:
        lines.append(f"\n⏳ Chờ duyệt ({len(pending)}):")
        for u in pending:
            lines.append(f"  • {u.full_name}")
            lines.append(f"    ID: {u.user_id}")
    
    if banned:
        lines.append(f"\n🚫 Đã cấm ({len(banned)}):")
        for u in banned:
            lines.append(f"  • {u.full_name}")
            lines.append(f"    ID: {u.user_id}")
    
    # Stats summary
    lines.append(f"\n━━━━━━━━━━━━━━━━━━━━")
    lines.append(f"Tổng: {len(users)} | Active: {len(active)} | Pending: {len(pending)} | Banned: {len(banned)}")
    
    await update.message.reply_text("\n".join(lines))


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
            "✅ Không có user nào đang chờ duyệt."
        )
        return
    
    await update.message.reply_text(
        f"⏳ Có {len(pending)} user đang chờ duyệt:"
    )
    
    for u in pending:
        await update.message.reply_text(
            f"Tên: {u.full_name}\n"
            f"ID: {u.user_id}\n"
            f"Thời gian đăng ký: {u.joined_at.strftime('%H:%M %d/%m/%Y')}",
            reply_markup=Keyboards.approve_reject_user(u.user_id)
        )


# =============================================================================
# BROADCAST COMMAND
# =============================================================================

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
    Example: /broadcast Hôm nay họp lúc 10h tại phòng họp A
    """
    if not context.args:
        await update.message.reply_text(
            "Sử dụng: /broadcast <tin nhắn>\n"
            "Ví dụ: /broadcast Hôm nay họp lúc 10h\n\n"
            "Tin nhắn sẽ được gửi đến tất cả nhân viên đang hoạt động."
        )
        return
    
    message = " ".join(context.args)
    
    # Get all active users
    active_users = UserService.get_active_users()
    
    if not active_users:
        await update.message.reply_text("Không có user nào đang hoạt động.")
        return
    
    # Confirm before sending
    await update.message.reply_text(
        f"📢 Sẽ gửi tin nhắn đến {len(active_users)} người:\n\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"{message}\n"
        f"━━━━━━━━━━━━━━━━━━━━\n\n"
        f"Đang gửi..."
    )
    
    # Send to all users
    success_count = 0
    fail_count = 0
    
    broadcast_message = (
        f"📢 THÔNG BÁO TỪ ADMIN\n"
        f"━━━━━━━━━━━━━━━━━━━━\n\n"
        f"{message}\n\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"🕐 {datetime.now().strftime('%H:%M %d/%m/%Y')}"
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
        f"✅ Đã gửi thành công: {success_count}\n"
        f"❌ Gửi thất bại: {fail_count}"
    )


# =============================================================================
# LOCATION MANAGEMENT COMMANDS
# =============================================================================

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
            "📍 Chưa có địa điểm nào được cấu hình.\n"
            "Sử dụng /set_location để thêm địa điểm."
        )
        return
    
    lines = ["📍 DANH SÁCH ĐỊA ĐIỂM\n"]
    
    for loc in locations:
        status = "✅ Active" if loc.is_active else "❌ Inactive"
        coords = GeolocationService.format_coordinates(
            loc.latitude, loc.longitude
        )
        maps_link = GeolocationService.get_google_maps_link(
            loc.latitude, loc.longitude
        )
        
        lines.append(
            f"\n{loc.id}. {loc.name}\n"
            f"   Tọa độ: {coords}\n"
            f"   Bán kính: {loc.radius}m\n"
            f"   Trạng thái: {status}\n"
            f"   Maps: {maps_link}"
        )
    
    await update.message.reply_text("\n".join(lines))


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
            "Sử dụng: /delete_location <id>\n"
            "Ví dụ: /delete_location 1\n\n"
            "Dùng /list_locations để xem danh sách ID."
        )
        return
    
    try:
        location_id = int(context.args[0])
    except ValueError:
        await update.message.reply_text("ID không hợp lệ.")
        return
    
    location = GeolocationService.get_location(location_id)
    if not location:
        await update.message.reply_text(f"Không tìm thấy địa điểm ID: {location_id}")
        return
    
    if GeolocationService.delete_location(location_id):
        await update.message.reply_text(
            f"✅ Đã vô hiệu hóa địa điểm: {location.name}"
        )
    else:
        await update.message.reply_text("Không thể xóa địa điểm.")


# =============================================================================
# REPORT COMMANDS
# =============================================================================

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
                "Sử dụng: /export_excel [tháng] [năm]\n"
                "Ví dụ: /export_excel 3 2024"
            )
            return
    
    status = await update.message.reply_text(
        f"⏳ Đang tạo báo cáo tháng {month}/{year}..."
    )
    
    try:
        excel_file = ExportService.generate_monthly_excel(year, month)
        filename = f"attendance_{year}_{month:02d}.xlsx"
        
        await update.message.reply_document(
            document=InputFile(excel_file, filename=filename),
            caption=f"📊 Báo cáo chấm công tháng {month}/{year}"
        )
        
        await status.delete()
        
    except Exception as e:
        logger.error(f"Export failed: {e}")
        await status.edit_text(f"❌ Lỗi: {str(e)}")


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
    
    stats_text = f"""📈 THỐNG KÊ HỆ THỐNG

👥 Nhân sự:
  • Tổng: {user_stats['total']}
  • Hoạt động: {user_stats['active']}
  • Chờ duyệt: {user_stats['pending']}
  • Đã cấm: {user_stats['banned']}
  • Admin: {user_stats['admins']}

📅 Hôm nay ({now.strftime('%d/%m/%Y')}):
  • Check-in: {today_report.checked_in}/{today_report.total_employees}
  • Đúng giờ: {today_report.on_time}
  • Muộn: {today_report.late}
  • Check-out: {today_report.checked_out}
"""
    
    await update.message.reply_text(stats_text)


# =============================================================================
# HELP COMMAND
# =============================================================================

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
    help_text = """🔧 LỆNH QUẢN TRỊ

👤 Quản lý User:
  /approve <id> - Duyệt user
  /reject <id> - Từ chối user
  /ban <id> - Cấm user
  /unban <id> - Bỏ cấm user
  /list_users - Danh sách user
  /list_pending - User chờ duyệt

📍 Quản lý Địa điểm:
  /set_location - Thêm địa điểm mới
  /list_locations - Danh sách địa điểm
  /delete_location <id> - Xóa địa điểm

📊 Báo cáo:
  /today - Báo cáo hôm nay
  /export_excel [tháng] [năm] - Xuất Excel
  /stats - Thống kê tổng hợp

📢 Khác:
  /broadcast <tin> - Gửi thông báo
  /help_admin - Trợ giúp này
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
            await query.edit_message_text("⚠️ Bạn không có quyền.")
            return
    
    data = query.data
    
    if data.startswith(CallbackData.APPROVE_USER):
        target_id = int(data.split(":")[1])
        target = UserService.get_user(target_id)
        
        if not target:
            await query.edit_message_text("User không tồn tại.")
            return
        
        if UserService.approve_user(target_id, user_id):
            await query.edit_message_text(f"✅ Đã duyệt: {target.full_name}")
            
            try:
                await context.bot.send_message(
                    chat_id=target_id,
                    text=Messages.REGISTRATION_APPROVED,
                    reply_markup=Keyboards.main_menu()
                )
            except Exception:
                pass
        else:
            await query.edit_message_text("Không thể duyệt user.")
    
    elif data.startswith(CallbackData.REJECT_USER):
        target_id = int(data.split(":")[1])
        target = UserService.get_user(target_id)
        
        if not target:
            await query.edit_message_text("User không tồn tại.")
            return
        
        name = target.full_name
        
        if UserService.reject_user(target_id, user_id):
            await query.edit_message_text(f"❌ Đã từ chối: {name}")
            
            try:
                await context.bot.send_message(
                    chat_id=target_id,
                    text=Messages.REGISTRATION_REJECTED
                )
            except Exception:
                pass
        else:
            await query.edit_message_text("Không thể từ chối user.")
    
    elif data == CallbackData.CANCEL:
        await query.edit_message_text("Đã hủy.")
```

---

## User Help Command

**File: `src/bot/handlers/help.py`**

```python
"""
Help command handler for all users.
"""

from telegram import Update
from telegram.ext import ContextTypes

from src.services.user_service import UserService
from src.database import UserRole


async def help_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
) -> None:
    """
    Show help based on user role.
    
    Usage: /help
    """
    user_id = update.effective_user.id
    user = UserService.get_user(user_id)
    
    # Basic help for all users
    basic_help = """📚 HƯỚNG DẪN SỬ DỤNG

🔹 Check-in/Check-out:
  • Nhấn nút "Check-in" hoặc /checkin
  • Gửi vị trí GPS khi được yêu cầu
  • Tương tự cho Check-out

🔹 Xem thông tin:
  /status - Trạng thái hôm nay
  /history - Lịch sử tháng này

🔹 Lưu ý:
  • Chỉ có thể check-in trong phạm vi văn phòng
  • Không thể dùng vị trí được forward
  • Vị trí phải được gửi trong vòng 60 giây
"""
    
    await update.message.reply_text(basic_help)
    
    # Admin additional help
    if user and user.role == UserRole.ADMIN:
        await update.message.reply_text(
            "💡 Bạn là Admin. Dùng /help_admin để xem lệnh quản trị."
        )
```

---

## Handler Registration Update

**Update `src/bot/__init__.py`:**

```python
def _register_handlers(app: Application) -> None:
    """Register all handlers."""
    
    # Import handlers
    from src.bot.handlers.start import registration_conversation
    from src.bot.handlers.checkin import (
        checkin_command, checkout_command,
        location_handler, status_command, history_command
    )
    from src.bot.handlers.location import (
        location_setup_conversation,
        list_locations_command, delete_location_command
    )
    from src.bot.handlers.admin import (
        approve_command, reject_command,
        ban_command, unban_command,
        list_users_command, list_pending_command,
        today_command, export_command, stats_command,
        broadcast_command, help_admin_command,
        admin_callback_handler
    )
    from src.bot.handlers.help import help_command
    from src.bot.handlers.menu import text_message_handler
    
    # Conversation handlers (must be first)
    app.add_handler(registration_conversation)
    app.add_handler(location_setup_conversation)
    
    # User commands
    app.add_handler(CommandHandler("checkin", checkin_command))
    app.add_handler(CommandHandler("checkout", checkout_command))
    app.add_handler(CommandHandler("status", status_command))
    app.add_handler(CommandHandler("history", history_command))
    app.add_handler(CommandHandler("help", help_command))
    
    # Admin commands
    app.add_handler(CommandHandler("approve", approve_command))
    app.add_handler(CommandHandler("reject", reject_command))
    app.add_handler(CommandHandler("ban", ban_command))
    app.add_handler(CommandHandler("unban", unban_command))
    app.add_handler(CommandHandler("list_users", list_users_command))
    app.add_handler(CommandHandler("list_pending", list_pending_command))
    app.add_handler(CommandHandler("list_locations", list_locations_command))
    app.add_handler(CommandHandler("delete_location", delete_location_command))
    app.add_handler(CommandHandler("today", today_command))
    app.add_handler(CommandHandler("export_excel", export_command))
    app.add_handler(CommandHandler("stats", stats_command))
    app.add_handler(CommandHandler("broadcast", broadcast_command))
    app.add_handler(CommandHandler("help_admin", help_admin_command))
    
    # Message handlers
    app.add_handler(MessageHandler(filters.LOCATION, location_handler))
    app.add_handler(MessageHandler(
        filters.TEXT & ~filters.COMMAND,
        text_message_handler
    ))
    
    # Callback handler
    app.add_handler(CallbackQueryHandler(admin_callback_handler))
```

---

## Bot Commands for BotFather

Register these commands with BotFather using `/setcommands`:

```
start - Bắt đầu / Đăng ký
checkin - Check-in điểm danh
checkout - Check-out kết thúc
status - Xem trạng thái hôm nay
history - Xem lịch sử tháng này
help - Hướng dẫn sử dụng
```

For admin scope (if using command scopes):

```
approve - Duyệt user mới
reject - Từ chối user
ban - Cấm user
unban - Bỏ cấm user
list_users - Danh sách user
list_pending - User chờ duyệt
set_location - Thêm địa điểm
list_locations - Danh sách địa điểm
delete_location - Xóa địa điểm
today - Báo cáo hôm nay
export_excel - Xuất báo cáo Excel
stats - Thống kê
broadcast - Gửi thông báo
help_admin - Trợ giúp admin
```

---

## Verification Checklist

Before proceeding to the tracker, verify:

- [ ] All admin commands implemented and working
- [ ] User management (approve/reject/ban/unban) works
- [ ] User listing shows correct information
- [ ] Location management works
- [ ] Reports generate correctly
- [ ] Broadcast sends to all active users
- [ ] Help commands show appropriate info
- [ ] Callback handlers work for inline buttons
- [ ] All handlers registered in application

---

## Next Steps

Proceed to `TRACKER.md` for the implementation tracker.
