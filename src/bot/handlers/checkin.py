"""
Check-in and check-out command handlers.

Handles the attendance recording flow including location requests
and validation.
"""

import logging
from datetime import datetime

from telegram import Update, Message
from telegram.ext import ContextTypes

from src.services.attendance import AttendanceService
from src.services.user_service import UserService
from src.services.geolocation import GeolocationService
from src.services.anti_cheat import AntiCheatService
from src.database import User, Location
from src.constants import Messages, KeyboardLabels
from src.bot.keyboards import Keyboards
from src.bot.middlewares import require_registration, require_active, log_action
from src.bot.handlers.help import check_muted
from src.config import config

logger = logging.getLogger(__name__)

# Store pending check-in/check-out state per user
# Key: user_id, Value: "checkin" or "checkout"
pending_actions = {}


# Ngày cho phép check-in: Thứ 2 (0) và Thứ 4 (2)
ALLOWED_WEEKDAYS = [0, 2]  # Monday = 0, Wednesday = 2

def get_vn_now():
    """Get current time in Vietnam timezone."""
    import pytz
    vn_tz = pytz.timezone('Asia/Ho_Chi_Minh')
    return datetime.now(vn_tz)

def is_checkin_day() -> bool:
    """Check if today is a valid check-in day (Monday or Wednesday) in Vietnam timezone."""
    return get_vn_now().weekday() in ALLOWED_WEEKDAYS

def is_after_work_start() -> bool:
    """Check if current time is after work start time (17:45)."""
    now_vn = get_vn_now()
    work_start_hour = config.attendance.work_start_hour
    work_start_minute = config.attendance.work_start_minute
    current_minutes = now_vn.hour * 60 + now_vn.minute
    work_start_minutes = work_start_hour * 60 + work_start_minute
    return current_minutes >= work_start_minutes

def get_weekday_name(weekday: int) -> str:
    """Get Vietnamese weekday name."""
    names = ["Thu 2", "Thu 3", "Thu 4", "Thu 5", "Thu 6", "Thu 7", "Chu Nhat"]
    return names[weekday]


@require_registration
@require_active
@log_action("request_checkin")
async def checkin_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    user: User = None
) -> None:
    """
    Handle /checkin command or "Check-in" button.
    
    Initiates the check-in flow by requesting user's location.
    """
    # Check if muted
    if await check_muted(update):
        return
    
    user_id = update.effective_user.id
    
    # Check if today is a valid check-in day
    if not is_checkin_day():
        await update.message.reply_text(
            "🙄 Ủa bro? Hôm nay có họp đâu mà điểm danh?\n\n"
            "📅 CLB chỉ họp Thứ 2 và Thứ 4 thôi nha!\n"
            "🛋️ Về chill đi, đừng có chăm quá! 😴💀",
            reply_markup=Keyboards.main_menu()
        )
        return
    
    # Check if it's after work start time
    if not is_after_work_start():
        await update.message.reply_text(
            "⏰ Ê chưa tới giờ họp mà bro!\n\n"
            "🌅 Sớm quá xá luôn! Họp lúc 17:45 cơ mà!\n"
            "☕ Đi uống trà sữa đợi tí rồi quay lại nha! 🧋✨",
            reply_markup=Keyboards.main_menu()
        )
        return
    
    # Check if already checked in today
    if AttendanceService.has_checked_in_today(user_id):
        existing = AttendanceService.get_today_checkin(user_id)
        await update.message.reply_text(
            f"🙄 Bro ơi điểm danh rồi còn điểm chi nữa?\n\n"
            f"🕐 Đã check lúc: {existing.timestamp.strftime('%H:%M')}\n\n"
            f"🧠 7 giây quên luôn á? Goldfish brain real! 🐟💀"
        )
        return
    
    # Check if any locations are configured
    locations = GeolocationService.get_active_locations()
    if not locations:
        await update.message.reply_text(
            "😱 Ủa chưa có địa điểm họp nào được set!\n\n"
            "📍 Admin ơi quên config location rồi kìa! 💀"
        )
        return
    
    # Store pending action
    pending_actions[user_id] = "checkin"
    
    # Request location
    await update.message.reply_text(
        "📍 Gửi location để điểm danh nè bro!\n\n"
        "⚠️ Đừng có fake loc nha, Bot slay lắm đó! 🕵️💅",
        reply_markup=Keyboards.request_location()
    )


@require_registration
@require_active
@log_action("request_checkout")
async def checkout_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    user: User = None
) -> None:
    """
    Handle /checkout command or "Check-out" button.
    
    Initiates the check-out flow by requesting user's location.
    """
    # Check if muted
    if await check_muted(update):
        return
    
    user_id = update.effective_user.id
    
    # Check if checked in today
    if not AttendanceService.has_checked_in_today(user_id):
        await update.message.reply_text(
            "🤨 Ủa? Check-out cái gì? Bro chưa điểm danh mà!\n\n"
            "🛏️ Đừng nói là cúp họp nằm nhà nha? Real sussy đó! 😏💀"
        )
        return
    
    # Check if already checked out today
    if AttendanceService.has_checked_out_today(user_id):
        await update.message.reply_text(
            "🙄 Bro check-out rồi còn check chi nữa?\n\n"
            "🏠 Go home bro! Sao vẫn còn ở đây? 🤔💀"
        )
        return
    
    # Store pending action
    pending_actions[user_id] = "checkout"
    
    # Request location
    await update.message.reply_text(
        "📍 Gửi location để check-out nè!\n\n"
        "🏃 Họp xong rồi hả? GG! 🎉",
        reply_markup=Keyboards.request_location()
    )


async def location_handler(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
) -> None:
    """
    Handle location messages from users.
    
    Processes the location for check-in or check-out based on
    the pending action state.
    """
    user_id = update.effective_user.id
    message = update.message
    location = message.location
    
    # Check if user is active
    user = UserService.get_user(user_id)
    user_status = user.status.value if hasattr(user.status, 'value') else str(user.status)
    if not user or user_status != "active":
        await message.reply_text(
            "😅 Oof! Acc của bro chưa được kích hoạt!\n\n"
            "⏳ Đợi Admin approve nha bestie! 🙏"
        )
        return
    
    # Check pending action
    action = pending_actions.get(user_id)
    if not action:
        # No pending action, might be unsolicited location
        await message.reply_text(
            "🤔 Ủa bro gửi location làm gì vậy?\n\n"
            "👆 Bấm nút Điểm danh hoặc Check-out trước rồi gửi nha!",
            reply_markup=Keyboards.main_menu()
        )
        return
    
    # Clear pending action
    del pending_actions[user_id]
    
    # =================================================================
    # ANTI-CHEAT VALIDATION
    # =================================================================
    
    # Check for forwarded message
    validation = AntiCheatService.validate_location_message(message)
    if not validation.is_valid:
        await message.reply_text(
            validation.error_message,
            reply_markup=Keyboards.main_menu()
        )
        logger.warning(
            f"Anti-cheat failed for user {user_id}: {validation.error_message}"
        )
        return
    
    # =================================================================
    # LOCATION VERIFICATION
    # =================================================================
    
    user_lat = location.latitude
    user_lon = location.longitude
    
    # Find nearest office location
    nearest = GeolocationService.find_nearest_location(user_lat, user_lon)
    
    if not nearest:
        await message.reply_text(
            "😱 Chưa có địa điểm họp nào được set!\n\n"
            "📍 Admin ơi config đi! 💀",
            reply_markup=Keyboards.main_menu()
        )
        return
    
    office_location, distance = nearest
    
    # Check if within radius
    if distance > office_location.radius:
        await message.reply_text(
            f"❌ Ối dồi ôi! Vệ tinh báo bro đang ở Sao Hỏa à? 🚀💀\n\n"
            f"📏 Khoảng cách: {round(distance)}m\n"
            f"📍 Địa điểm họp: {office_location.name}\n"
            f"🎯 Bán kính cho phép: {office_location.radius}m\n\n"
            f"🏃‍♂️ Di chuyển lại gần đi bro!\n"
            f"🧋 Bot chỉ ngửi thấy mùi trà sữa, không thấy phòng họp!",
            reply_markup=Keyboards.main_menu()
        )
        return
    
    # =================================================================
    # PROCESS CHECK-IN OR CHECK-OUT
    # =================================================================
    
    if action == "checkin":
        await process_checkin(
            message, user_id, office_location, 
            user_lat, user_lon, distance
        )
    elif action == "checkout":
        await process_checkout(
            message, user_id, office_location,
            user_lat, user_lon, distance
        )


async def process_checkin(
    message: Message,
    user_id: int,
    location: Location,
    user_lat: float,
    user_lon: float,
    distance: float
) -> None:
    """
    Process a check-in after location validation.
    """
    result = AttendanceService.record_checkin(
        user_id=user_id,
        location_id=location.id,
        user_lat=user_lat,
        user_lon=user_lon,
        distance=distance
    )
    
    if result.success:
        if result.is_late:
            response = (
                f"⚠️ Điểm danh thành công... nhưng MUỘN rồi bro! 😤\n\n"
                f"🕐 Time: {result.attendance_log.timestamp.strftime('%H:%M')}\n"
                f"📍 Location: {location.name}\n"
                f"📏 Khoảng cách: {round(distance)}m\n"
                f"⏰ Muộn: {result.late_minutes} phút\n\n"
                f"🐌 Lần sau đi sớm hơn nha! Chậm như rùa! 💀"
            )
        else:
            response = (
                f"✅ SHEESH! Điểm danh thành công! 🔥\n\n"
                f"🕐 Time: {result.attendance_log.timestamp.strftime('%H:%M')}\n"
                f"📍 Location: {location.name}\n"
                f"📏 Khoảng cách: {round(distance)}m\n\n"
                f"💪 Bro chăm xỉu! Based! 🫡"
            )
    else:
        response = f"❌ Oof! {result.message} 💀"
    
    await message.reply_text(
        response,
        reply_markup=Keyboards.main_menu()
    )


async def process_checkout(
    message: Message,
    user_id: int,
    location: Location,
    user_lat: float,
    user_lon: float,
    distance: float
) -> None:
    """
    Process a check-out after location validation.
    """
    result = AttendanceService.record_checkout(
        user_id=user_id,
        location_id=location.id if location else None,
        user_lat=user_lat,
        user_lon=user_lon,
        distance=distance
    )
    
    if result.success:
        work_hours = AttendanceService.format_duration(result.work_duration)
        response = (
            f"✅ NICE! Check-out thành công! 🎉\n\n"
            f"🕐 Time: {result.attendance_log.timestamp.strftime('%H:%M')}\n"
            f"⏱️ Thời gian họp: {work_hours}\n\n"
            f"🛋️ Về chill thôi bro! GG! 🍻✨"
        )
    else:
        response = f"❌ Oof! {result.message} 💀"
    
    await message.reply_text(
        response,
        reply_markup=Keyboards.main_menu()
    )


async def cancel_action(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
) -> None:
    """Handle cancel button press."""
    user_id = update.effective_user.id
    
    # Clear any pending action
    if user_id in pending_actions:
        del pending_actions[user_id]
    
    await update.message.reply_text(
        "❌ Đã cancel! Nhát quá bro ơi! 😏🐔",
        reply_markup=Keyboards.main_menu()
    )


async def status_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
) -> None:
    """
    Handle /status command.
    
    Shows user's current attendance status for today.
    """
    # Check if muted
    if await check_muted(update):
        return
    
    user_id = update.effective_user.id
    user = UserService.get_user(user_id)
    
    if not user:
        await update.message.reply_text(
            "🤔 Ủa bro chưa đăng ký mà?\n\n"
            "👆 Dùng /start để đăng ký nha!"
        )
        return
    
    # Get today's attendance
    attendance = AttendanceService.get_user_attendance_today(user_id)
    
    # Build status message
    user_role = user.role.value if hasattr(user.role, 'value') else str(user.role)
    user_status = user.status.value if hasattr(user.status, 'value') else str(user.status)
    role = "👑 Admin" if user_role == "admin" else "👤 Member"
    status_text = (
        f"📊 THÔNG TIN TÀI KHOẢN\n\n"
        f"👤 Name: {user.full_name}\n"
        f"🎭 Role: {role}\n"
        f"📋 Status: {user_status}\n"
        f"📅 Joined: {user.joined_at.strftime('%d/%m/%Y')}"
    )
    
    today_text = f"\n\n🗓️ HÔM NAY ({datetime.now().strftime('%d/%m/%Y')}):\n"
    
    if attendance and attendance.check_in_time:
        checkin_str = attendance.check_in_time.strftime("%H:%M")
        checkout_str = attendance.check_out_time.strftime("%H:%M") if attendance.check_out_time else "Chưa checkout"
        
        today_text += f"  ⏰ Điểm danh: {checkin_str}\n"
        today_text += f"  🏃 Check-out: {checkout_str}\n"
        
        if attendance.is_late:
            today_text += f"  🐌 Đi muộn: {attendance.late_minutes} phút 💀\n"
        
        if attendance.work_duration:
            duration_str = AttendanceService.format_duration(attendance.work_duration)
            today_text += f"  ⏱️ Thời gian: {duration_str}"
        
        today_text += "\n\n💪 Bro chăm xỉu! Based! 🫡"
    else:
        today_text += "  ❌ Chưa điểm danh!\n\n"
        today_text += "🛏️ Định cúp họp hả? Dậy đi bro! 💀"
    
    await update.message.reply_text(
        f"{status_text}{today_text}",
        reply_markup=Keyboards.main_menu()
    )


async def history_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
) -> None:
    """
    Handle /history command.
    
    Shows user's attendance history for the current month.
    """
    # Check if muted
    if await check_muted(update):
        return
    
    user_id = update.effective_user.id
    user = UserService.get_user(user_id)
    
    if not user:
        await update.message.reply_text(
            "🤔 Ủa bro chưa đăng ký mà?\n\n"
            "👆 Dùng /start để đăng ký nha!"
        )
        return
    
    # Get current month summary
    now = datetime.now()
    summary = AttendanceService.get_monthly_summary(
        user_id, now.year, now.month
    )
    
    history_text = (
        f"📜 LỊCH SỬ ĐIỂM DANH THÁNG {now.month}/{now.year}\n\n"
        f"📅 Tổng số ngày họp: {summary['total_days']}\n"
        f"✅ Số ngày đi họp: {summary['present_days']}\n"
        f"🐌 Số ngày đi muộn: {summary['late_days']}\n"
        f"❌ Số ngày cúp họp: {summary['absent_days']}\n"
        f"⏱️ Tổng giờ họp: {summary['total_work_hours']}h\n"
        f"📊 Trung bình/ngày: {summary['average_work_hours']}h\n\n"
    )
    
    if summary['absent_days'] > 0:
        history_text += f"😤 Bro cúp họp {summary['absent_days']} ngày là sao? 💀"
    elif summary['late_days'] > 0:
        history_text += f"🐌 Muộn {summary['late_days']} lần rồi đó, cố gắng lên bro! 😏"
    else:
        history_text += "💪 Bro chăm xỉu! Perfect attendance! 🔥🫡"
    
    await update.message.reply_text(
        history_text,
        reply_markup=Keyboards.main_menu()
    )
