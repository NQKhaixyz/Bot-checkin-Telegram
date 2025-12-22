"""
Report command handlers for admin users.

Handles daily reports, Excel exports, and statistics.
"""

import logging
from datetime import datetime, date
from io import BytesIO

from telegram import Update, InputFile
from telegram.ext import ContextTypes

from src.services.export import ExportService
from src.services.user_service import UserService
from src.database import User, get_db_session, AttendanceLog, AttendanceType
from src.bot.keyboards import Keyboards
from src.bot.middlewares import require_admin, require_registration, log_action
from sqlalchemy import func

logger = logging.getLogger(__name__)


@require_registration
@require_admin
@log_action("today_report")
async def today_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    user: User = None
) -> None:
    """
    Handle /today command.
    
    Shows today's attendance summary.
    """
    # Generate report
    report = ExportService.get_daily_report()
    
    # Format as text
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
    Handle /export_excel [month] [year] command.
    
    Generates and sends Excel attendance report.
    
    Usage:
        /export_excel          - Current month
        /export_excel 3        - March of current year
        /export_excel 3 2024   - March 2024
    """
    now = datetime.now()
    year = now.year
    month = now.month
    
    # Parse arguments
    if context.args:
        try:
            month = int(context.args[0])
            if month < 1 or month > 12:
                raise ValueError("Invalid month")
            
            if len(context.args) > 1:
                year = int(context.args[1])
                if year < 2000 or year > 2100:
                    raise ValueError("Invalid year")
        except ValueError:
            await update.message.reply_text(
                "Su dung: /export_excel [thang] [nam]\n"
                "Vi du:\n"
                "  /export_excel        - Thang hien tai\n"
                "  /export_excel 3      - Thang 3 nam nay\n"
                "  /export_excel 3 2024 - Thang 3/2024"
            )
            return
    
    # Send "generating" message
    status_message = await update.message.reply_text(
        f"Dang tao bao cao thang {month}/{year}..."
    )
    
    try:
        # Generate Excel file
        excel_file = ExportService.generate_monthly_excel(year, month)
        
        # Create filename
        filename = f"attendance_{year}_{month:02d}.xlsx"
        
        # Send file
        await update.message.reply_document(
            document=InputFile(excel_file, filename=filename),
            caption=f"Bao cao cham cong thang {month}/{year}"
        )
        
        # Delete status message
        await status_message.delete()
        
        logger.info(
            f"Admin {user.user_id if user else 'unknown'} exported report for {month}/{year}"
        )
        
    except Exception as e:
        logger.error(f"Failed to generate report: {e}")
        await status_message.edit_text(
            f"Loi khi tao bao cao: {str(e)}"
        )


@require_registration
@require_admin
async def export_csv_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    user: User = None
) -> None:
    """
    Handle /export_csv [month] [year] command.
    
    Generates and sends CSV attendance report.
    """
    now = datetime.now()
    year = now.year
    month = now.month
    
    # Parse arguments (same as export_excel)
    if context.args:
        try:
            month = int(context.args[0])
            if len(context.args) > 1:
                year = int(context.args[1])
        except ValueError:
            await update.message.reply_text(
                "Su dung: /export_csv [thang] [nam]"
            )
            return
    
    try:
        # Generate CSV
        csv_content = ExportService.generate_csv_report(year, month)
        
        # Create file
        csv_file = BytesIO(csv_content.encode('utf-8-sig'))  # BOM for Excel
        filename = f"attendance_{year}_{month:02d}.csv"
        
        await update.message.reply_document(
            document=InputFile(csv_file, filename=filename),
            caption=f"Bao cao CSV thang {month}/{year}"
        )
        
    except Exception as e:
        logger.error(f"Failed to generate CSV: {e}")
        await update.message.reply_text(f"Loi: {str(e)}")


@require_registration
@require_admin
async def stats_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    user: User = None
) -> None:
    """
    Handle /stats command.
    
    Shows overall attendance statistics.
    """
    now = datetime.now()
    
    # Get user stats
    user_stats = UserService.get_user_stats()
    
    # Get today's report
    today_report = ExportService.get_daily_report()
    
    # Calculate attendance rate for current month
    total_possible = user_stats["active"] * now.day  # Working days so far
    
    with get_db_session() as db:
        actual_checkins = db.query(func.count(AttendanceLog.id)).filter(
            AttendanceLog.type == AttendanceType.IN,
            func.extract('month', AttendanceLog.timestamp) == now.month,
            func.extract('year', AttendanceLog.timestamp) == now.year
        ).scalar()
    
    attendance_rate = (actual_checkins / total_possible * 100) if total_possible > 0 else 0
    
    stats_text = f"""THONG KE TONG HOP

Nhan su:
  - Tong so: {user_stats['total']}
  - Dang hoat dong: {user_stats['active']}
  - Cho duyet: {user_stats['pending']}
  - Da cam: {user_stats['banned']}
  - Quan tri vien: {user_stats['admins']}

Hom nay ({now.strftime('%d/%m/%Y')}):
  - Da check-in: {today_report.checked_in}/{today_report.total_employees}
  - Dung gio: {today_report.on_time}
  - Di muon: {today_report.late}
  - Da check-out: {today_report.checked_out}

Thang {now.month}/{now.year}:
  - Tong luot check-in: {actual_checkins}
  - Ti le chuyen can: {attendance_rate:.1f}%
"""
    
    await update.message.reply_text(stats_text)
