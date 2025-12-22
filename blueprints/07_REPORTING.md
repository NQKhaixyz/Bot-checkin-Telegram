# Reporting System Implementation Guide

## Overview

This guide covers the implementation of the reporting and export system including daily reports, monthly Excel exports, real-time statistics, and optional Google Sheets integration.

---

## Prerequisites

- Database models implemented (01_DATABASE_SCHEMA.md)
- Attendance service implemented (04_ATTENDANCE_SYSTEM.md)
- User service implemented (03_USER_MANAGEMENT.md)

---

## Report Types

### 1. Daily Report (`/today`)
- Shows who has checked in today
- Who is late
- Who hasn't checked in yet

### 2. Monthly Excel Export (`/export_excel`)
- Detailed attendance for each employee
- Summary statistics
- Formatted spreadsheet with multiple sheets

### 3. Real-time Statistics
- Live attendance counts
- Weekly/monthly summaries

---

## Implementation Steps

### Step 1: Create Export Service

**File: `src/services/export.py`**

```python
"""
Export service for generating attendance reports.

Supports:
- Excel (.xlsx) file generation
- CSV export
- Google Sheets sync (optional)
"""

import logging
import io
from datetime import datetime, date, timedelta
from typing import List, Dict, Optional, BinaryIO
from calendar import monthrange
from dataclasses import dataclass

from openpyxl import Workbook
from openpyxl.styles import (
    Font, Alignment, Border, Side, PatternFill,
    NamedStyle
)
from openpyxl.utils import get_column_letter
from sqlalchemy import func

from src.database import (
    User, AttendanceLog, AttendanceType, UserStatus,
    get_db_session
)
from src.services.attendance import AttendanceService
from src.services.user_service import UserService
from src.config import config

logger = logging.getLogger(__name__)


@dataclass
class DailyReportData:
    """Data for daily attendance report."""
    date: date
    total_employees: int
    checked_in: int
    on_time: int
    late: int
    not_checked_in: int
    checked_out: int
    present_users: List[Dict]
    absent_users: List[Dict]
    late_users: List[Dict]


@dataclass
class MonthlyReportData:
    """Data for monthly attendance report."""
    year: int
    month: int
    employee_data: List[Dict]
    summary: Dict


class ExportService:
    """Service class for generating reports and exports."""
    
    # Excel styles
    HEADER_FILL = PatternFill(
        start_color="4472C4",
        end_color="4472C4",
        fill_type="solid"
    )
    HEADER_FONT = Font(bold=True, color="FFFFFF")
    LATE_FILL = PatternFill(
        start_color="FFC7CE",
        end_color="FFC7CE",
        fill_type="solid"
    )
    ABSENT_FILL = PatternFill(
        start_color="FFEB9C",
        end_color="FFEB9C",
        fill_type="solid"
    )
    THIN_BORDER = Border(
        left=Side(style='thin'),
        right=Side(style='thin'),
        top=Side(style='thin'),
        bottom=Side(style='thin')
    )
    
    @staticmethod
    def get_daily_report(target_date: date = None) -> DailyReportData:
        """
        Generate daily attendance report data.
        
        Args:
            target_date: Date to report on (defaults to today)
            
        Returns:
            DailyReportData with all attendance information
        """
        if target_date is None:
            target_date = AttendanceService.get_current_time().date()
        
        # Get all active users
        active_users = UserService.get_active_users()
        total_employees = len(active_users)
        
        # Get today's attendance logs
        with get_db_session() as db:
            logs = db.query(AttendanceLog).filter(
                func.date(AttendanceLog.timestamp) == target_date
            ).all()
            
            # Create lookup by user_id
            checkins = {
                log.user_id: log 
                for log in logs 
                if log.type == AttendanceType.IN
            }
            checkouts = {
                log.user_id: log 
                for log in logs 
                if log.type == AttendanceType.OUT
            }
        
        # Categorize users
        present_users = []
        absent_users = []
        late_users = []
        
        for user in active_users:
            checkin = checkins.get(user.user_id)
            checkout = checkouts.get(user.user_id)
            
            user_data = {
                "user_id": user.user_id,
                "name": user.full_name,
                "checkin_time": checkin.timestamp if checkin else None,
                "checkout_time": checkout.timestamp if checkout else None,
                "is_late": checkin.is_late if checkin else False,
                "distance": checkin.distance if checkin else None
            }
            
            if checkin:
                present_users.append(user_data)
                if checkin.is_late:
                    late_users.append(user_data)
            else:
                absent_users.append(user_data)
        
        return DailyReportData(
            date=target_date,
            total_employees=total_employees,
            checked_in=len(present_users),
            on_time=len(present_users) - len(late_users),
            late=len(late_users),
            not_checked_in=len(absent_users),
            checked_out=len(checkouts),
            present_users=present_users,
            absent_users=absent_users,
            late_users=late_users
        )
    
    @staticmethod
    def format_daily_report(report: DailyReportData) -> str:
        """
        Format daily report as text message.
        
        Args:
            report: DailyReportData object
            
        Returns:
            Formatted string for Telegram message
        """
        lines = [
            f"📊 BÁO CÁO NGÀY {report.date.strftime('%d/%m/%Y')}",
            f"━━━━━━━━━━━━━━━━━━━━",
            f"",
            f"👥 Tổng nhân viên: {report.total_employees}",
            f"✅ Đã check-in: {report.checked_in}",
            f"⏰ Đúng giờ: {report.on_time}",
            f"⚠️ Đi muộn: {report.late}",
            f"❌ Chưa check-in: {report.not_checked_in}",
            f"🚪 Đã check-out: {report.checked_out}",
        ]
        
        # Add late users
        if report.late_users:
            lines.append(f"\n⚠️ DANH SÁCH ĐI MUỘN:")
            for user in report.late_users:
                time_str = user["checkin_time"].strftime("%H:%M")
                lines.append(f"  • {user['name']} - {time_str}")
        
        # Add absent users
        if report.absent_users:
            lines.append(f"\n❌ CHƯA CHECK-IN:")
            for user in report.absent_users:
                lines.append(f"  • {user['name']}")
        
        return "\n".join(lines)
    
    @staticmethod
    def generate_monthly_excel(
        year: int,
        month: int
    ) -> BinaryIO:
        """
        Generate monthly Excel attendance report.
        
        Creates a workbook with:
        - Summary sheet
        - Detailed attendance sheet
        - Statistics sheet
        
        Args:
            year: Year
            month: Month (1-12)
            
        Returns:
            BytesIO object containing the Excel file
        """
        _, days_in_month = monthrange(year, month)
        start_date = date(year, month, 1)
        end_date = date(year, month, days_in_month)
        
        # Get all active users
        users = UserService.get_active_users()
        
        # Get all attendance logs for the month
        with get_db_session() as db:
            logs = db.query(AttendanceLog).filter(
                func.date(AttendanceLog.timestamp) >= start_date,
                func.date(AttendanceLog.timestamp) <= end_date
            ).all()
        
        # Organize logs by user and date
        attendance_map = {}  # (user_id, date) -> {in: log, out: log}
        for log in logs:
            key = (log.user_id, log.timestamp.date())
            if key not in attendance_map:
                attendance_map[key] = {"in": None, "out": None}
            
            if log.type == AttendanceType.IN:
                attendance_map[key]["in"] = log
            else:
                attendance_map[key]["out"] = log
        
        # Create workbook
        wb = Workbook()
        
        # =====================================================================
        # Sheet 1: Summary
        # =====================================================================
        ws_summary = wb.active
        ws_summary.title = "Tóm tắt"
        
        # Header
        ws_summary.append([f"BÁO CÁO CHẤM CÔNG THÁNG {month}/{year}"])
        ws_summary.merge_cells("A1:E1")
        ws_summary["A1"].font = Font(bold=True, size=14)
        ws_summary["A1"].alignment = Alignment(horizontal="center")
        
        ws_summary.append([])
        ws_summary.append([
            "STT", "Họ và Tên", "Số ngày đi làm", 
            "Số ngày muộn", "Tổng phút muộn"
        ])
        
        # Style header row
        for col in range(1, 6):
            cell = ws_summary.cell(row=3, column=col)
            cell.fill = ExportService.HEADER_FILL
            cell.font = ExportService.HEADER_FONT
            cell.border = ExportService.THIN_BORDER
            cell.alignment = Alignment(horizontal="center")
        
        # Data rows
        row_num = 4
        for idx, user in enumerate(users, 1):
            # Calculate statistics for user
            total_days = 0
            late_days = 0
            total_late_minutes = 0
            
            for day in range(1, days_in_month + 1):
                current_date = date(year, month, day)
                key = (user.user_id, current_date)
                
                if key in attendance_map and attendance_map[key]["in"]:
                    total_days += 1
                    checkin = attendance_map[key]["in"]
                    if checkin.is_late:
                        late_days += 1
                        _, minutes = AttendanceService.is_late(
                            checkin.timestamp
                        )
                        total_late_minutes += minutes
            
            ws_summary.append([
                idx,
                user.full_name,
                total_days,
                late_days,
                total_late_minutes
            ])
            
            # Apply borders
            for col in range(1, 6):
                cell = ws_summary.cell(row=row_num, column=col)
                cell.border = ExportService.THIN_BORDER
            
            row_num += 1
        
        # Adjust column widths
        ws_summary.column_dimensions["A"].width = 5
        ws_summary.column_dimensions["B"].width = 25
        ws_summary.column_dimensions["C"].width = 15
        ws_summary.column_dimensions["D"].width = 15
        ws_summary.column_dimensions["E"].width = 15
        
        # =====================================================================
        # Sheet 2: Chi tiết
        # =====================================================================
        ws_detail = wb.create_sheet("Chi tiết")
        
        # Header row 1: Employee names
        header1 = ["Ngày"]
        for user in users:
            header1.extend([user.full_name, ""])  # 2 columns per user
        ws_detail.append(header1)
        
        # Header row 2: In/Out labels
        header2 = [""]
        for _ in users:
            header2.extend(["Giờ vào", "Giờ ra"])
        ws_detail.append(header2)
        
        # Style headers
        for row in [1, 2]:
            for col in range(1, len(header1) + 1):
                cell = ws_detail.cell(row=row, column=col)
                cell.fill = ExportService.HEADER_FILL
                cell.font = ExportService.HEADER_FONT
                cell.border = ExportService.THIN_BORDER
                cell.alignment = Alignment(horizontal="center")
        
        # Merge employee name cells
        col_idx = 2
        for _ in users:
            ws_detail.merge_cells(
                start_row=1, start_column=col_idx,
                end_row=1, end_column=col_idx + 1
            )
            col_idx += 2
        
        # Data rows (one per day)
        for day in range(1, days_in_month + 1):
            current_date = date(year, month, day)
            row_data = [current_date.strftime("%d/%m")]
            
            for user in users:
                key = (user.user_id, current_date)
                attendance = attendance_map.get(key, {"in": None, "out": None})
                
                checkin = attendance["in"]
                checkout = attendance["out"]
                
                in_time = checkin.timestamp.strftime("%H:%M") if checkin else "-"
                out_time = checkout.timestamp.strftime("%H:%M") if checkout else "-"
                
                row_data.extend([in_time, out_time])
            
            ws_detail.append(row_data)
            
            # Style data row
            row_num = day + 2
            for col in range(1, len(row_data) + 1):
                cell = ws_detail.cell(row=row_num, column=col)
                cell.border = ExportService.THIN_BORDER
                cell.alignment = Alignment(horizontal="center")
                
                # Highlight late arrivals
                if col > 1 and (col - 2) % 2 == 0:  # Check-in columns
                    user_idx = (col - 2) // 2
                    if user_idx < len(users):
                        user = users[user_idx]
                        key = (user.user_id, current_date)
                        if key in attendance_map:
                            checkin = attendance_map[key].get("in")
                            if checkin and checkin.is_late:
                                cell.fill = ExportService.LATE_FILL
        
        # Adjust column widths
        ws_detail.column_dimensions["A"].width = 10
        for col in range(2, len(header1) + 1):
            ws_detail.column_dimensions[get_column_letter(col)].width = 10
        
        # =====================================================================
        # Save to BytesIO
        # =====================================================================
        output = io.BytesIO()
        wb.save(output)
        output.seek(0)
        
        logger.info(f"Generated Excel report for {month}/{year}")
        
        return output
    
    @staticmethod
    def generate_csv_report(
        year: int,
        month: int
    ) -> str:
        """
        Generate CSV attendance report.
        
        Args:
            year: Year
            month: Month (1-12)
            
        Returns:
            CSV string
        """
        import csv
        import io
        
        _, days_in_month = monthrange(year, month)
        start_date = date(year, month, 1)
        end_date = date(year, month, days_in_month)
        
        # Get data (similar to Excel generation)
        users = UserService.get_active_users()
        
        with get_db_session() as db:
            logs = db.query(AttendanceLog).filter(
                func.date(AttendanceLog.timestamp) >= start_date,
                func.date(AttendanceLog.timestamp) <= end_date
            ).all()
        
        # Create CSV
        output = io.StringIO()
        writer = csv.writer(output)
        
        # Header
        writer.writerow([
            "Ngày", "Họ tên", "Giờ vào", "Giờ ra", 
            "Đi muộn", "Phút muộn"
        ])
        
        # Data
        for day in range(1, days_in_month + 1):
            current_date = date(year, month, day)
            
            for user in users:
                checkin = None
                checkout = None
                
                for log in logs:
                    if (log.user_id == user.user_id and 
                        log.timestamp.date() == current_date):
                        if log.type == AttendanceType.IN:
                            checkin = log
                        else:
                            checkout = log
                
                late_minutes = 0
                if checkin and checkin.is_late:
                    _, late_minutes = AttendanceService.is_late(
                        checkin.timestamp
                    )
                
                writer.writerow([
                    current_date.strftime("%d/%m/%Y"),
                    user.full_name,
                    checkin.timestamp.strftime("%H:%M") if checkin else "",
                    checkout.timestamp.strftime("%H:%M") if checkout else "",
                    "Có" if checkin and checkin.is_late else "",
                    late_minutes if late_minutes > 0 else ""
                ])
        
        return output.getvalue()
```

### Step 2: Create Report Handler

**File: `src/bot/handlers/report.py`**

```python
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
from src.database import User
from src.bot.keyboards import Keyboards
from src.bot.middlewares import require_admin, log_action

logger = logging.getLogger(__name__)


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
                "Sử dụng: /export_excel [tháng] [năm]\n"
                "Ví dụ:\n"
                "  /export_excel        - Tháng hiện tại\n"
                "  /export_excel 3      - Tháng 3 năm nay\n"
                "  /export_excel 3 2024 - Tháng 3/2024"
            )
            return
    
    # Send "generating" message
    status_message = await update.message.reply_text(
        f"Đang tạo báo cáo tháng {month}/{year}..."
    )
    
    try:
        # Generate Excel file
        excel_file = ExportService.generate_monthly_excel(year, month)
        
        # Create filename
        filename = f"attendance_{year}_{month:02d}.xlsx"
        
        # Send file
        await update.message.reply_document(
            document=InputFile(excel_file, filename=filename),
            caption=f"📊 Báo cáo chấm công tháng {month}/{year}"
        )
        
        # Delete status message
        await status_message.delete()
        
        logger.info(
            f"Admin {user.user_id} exported report for {month}/{year}"
        )
        
    except Exception as e:
        logger.error(f"Failed to generate report: {e}")
        await status_message.edit_text(
            f"Lỗi khi tạo báo cáo: {str(e)}"
        )


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
                "Sử dụng: /export_csv [tháng] [năm]"
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
            caption=f"📊 Báo cáo CSV tháng {month}/{year}"
        )
        
    except Exception as e:
        logger.error(f"Failed to generate CSV: {e}")
        await update.message.reply_text(f"Lỗi: {str(e)}")


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
    from src.services.user_service import UserService
    from src.services.attendance import AttendanceService
    
    now = datetime.now()
    
    # Get user stats
    user_stats = UserService.get_user_stats()
    
    # Get today's report
    today_report = ExportService.get_daily_report()
    
    # Calculate attendance rate for current month
    total_possible = user_stats["active"] * now.day  # Working days so far
    
    with get_db_session() as db:
        from src.database import AttendanceLog, AttendanceType
        from sqlalchemy import func
        
        actual_checkins = db.query(func.count(AttendanceLog.id)).filter(
            AttendanceLog.type == AttendanceType.IN,
            func.extract('month', AttendanceLog.timestamp) == now.month,
            func.extract('year', AttendanceLog.timestamp) == now.year
        ).scalar()
    
    attendance_rate = (actual_checkins / total_possible * 100) if total_possible > 0 else 0
    
    stats_text = f"""📈 THỐNG KÊ TỔNG HỢP

👥 Nhân sự:
  • Tổng số: {user_stats['total']}
  • Đang hoạt động: {user_stats['active']}
  • Chờ duyệt: {user_stats['pending']}
  • Đã cấm: {user_stats['banned']}
  • Quản trị viên: {user_stats['admins']}

📅 Hôm nay ({now.strftime('%d/%m/%Y')}):
  • Đã check-in: {today_report.checked_in}/{today_report.total_employees}
  • Đúng giờ: {today_report.on_time}
  • Đi muộn: {today_report.late}
  • Đã check-out: {today_report.checked_out}

📊 Tháng {now.month}/{now.year}:
  • Tổng lượt check-in: {actual_checkins}
  • Tỷ lệ chuyên cần: {attendance_rate:.1f}%
"""
    
    await update.message.reply_text(stats_text)
```

### Step 3: Optional Google Sheets Integration

**File: `src/services/google_sheets.py`**

```python
"""
Google Sheets integration for real-time attendance sync.

Optional feature - requires Google API credentials.
"""

import logging
from datetime import datetime, date
from typing import List, Dict, Optional

logger = logging.getLogger(__name__)

try:
    import gspread
    from oauth2client.service_account import ServiceAccountCredentials
    GSPREAD_AVAILABLE = True
except ImportError:
    GSPREAD_AVAILABLE = False
    logger.warning("gspread not installed. Google Sheets sync disabled.")


class GoogleSheetsService:
    """Service for syncing attendance data to Google Sheets."""
    
    SCOPES = [
        'https://spreadsheets.google.com/feeds',
        'https://www.googleapis.com/auth/drive'
    ]
    
    def __init__(
        self,
        credentials_path: str,
        spreadsheet_id: str
    ):
        """
        Initialize Google Sheets service.
        
        Args:
            credentials_path: Path to Google API credentials JSON
            spreadsheet_id: ID of the target spreadsheet
        """
        if not GSPREAD_AVAILABLE:
            raise ImportError("gspread package required for Google Sheets")
        
        self.credentials_path = credentials_path
        self.spreadsheet_id = spreadsheet_id
        self._client = None
        self._spreadsheet = None
    
    def _get_client(self):
        """Get or create authenticated gspread client."""
        if self._client is None:
            credentials = ServiceAccountCredentials.from_json_keyfile_name(
                self.credentials_path,
                self.SCOPES
            )
            self._client = gspread.authorize(credentials)
        return self._client
    
    def _get_spreadsheet(self):
        """Get or open the target spreadsheet."""
        if self._spreadsheet is None:
            client = self._get_client()
            self._spreadsheet = client.open_by_key(self.spreadsheet_id)
        return self._spreadsheet
    
    def sync_daily_attendance(
        self,
        attendance_data: List[Dict]
    ) -> bool:
        """
        Sync daily attendance to Google Sheets.
        
        Args:
            attendance_data: List of attendance records
            
        Returns:
            True if sync successful
        """
        try:
            spreadsheet = self._get_spreadsheet()
            
            # Get or create today's worksheet
            today = date.today().strftime("%Y-%m-%d")
            
            try:
                worksheet = spreadsheet.worksheet(today)
            except gspread.WorksheetNotFound:
                worksheet = spreadsheet.add_worksheet(
                    title=today,
                    rows=100,
                    cols=10
                )
                # Add headers
                worksheet.update('A1:F1', [[
                    'Họ tên', 'Giờ vào', 'Giờ ra', 
                    'Đi muộn', 'Phút muộn', 'Ghi chú'
                ]])
            
            # Prepare data rows
            rows = []
            for record in attendance_data:
                rows.append([
                    record.get('name', ''),
                    record.get('checkin_time', ''),
                    record.get('checkout_time', ''),
                    'Có' if record.get('is_late') else '',
                    record.get('late_minutes', ''),
                    record.get('note', '')
                ])
            
            # Update sheet
            if rows:
                worksheet.update(f'A2:F{len(rows)+1}', rows)
            
            logger.info(f"Synced {len(rows)} records to Google Sheets")
            return True
            
        except Exception as e:
            logger.error(f"Google Sheets sync failed: {e}")
            return False
    
    def get_sheet_url(self) -> str:
        """Get URL to the spreadsheet."""
        return f"https://docs.google.com/spreadsheets/d/{self.spreadsheet_id}"
```

---

## Testing Export Service

```python
"""Test file: tests/test_export.py"""

import pytest
from datetime import date, datetime
from io import BytesIO

from src.services.export import ExportService, DailyReportData
from src.database import init_db


@pytest.fixture
def setup_db():
    """Initialize test database with sample data."""
    init_db("sqlite:///:memory:")
    
    from src.services.user_service import UserService
    from src.database import UserStatus
    
    # Create test users
    UserService.create_user(1, "User One", status=UserStatus.ACTIVE)
    UserService.create_user(2, "User Two", status=UserStatus.ACTIVE)
    UserService.create_user(3, "User Three", status=UserStatus.ACTIVE)
    
    yield


def test_daily_report_empty(setup_db):
    """Test daily report with no attendance."""
    report = ExportService.get_daily_report()
    
    assert report.total_employees == 3
    assert report.checked_in == 0
    assert report.not_checked_in == 3


def test_daily_report_format(setup_db):
    """Test daily report formatting."""
    report = DailyReportData(
        date=date.today(),
        total_employees=10,
        checked_in=8,
        on_time=6,
        late=2,
        not_checked_in=2,
        checked_out=5,
        present_users=[],
        absent_users=[],
        late_users=[]
    )
    
    formatted = ExportService.format_daily_report(report)
    
    assert "Tổng nhân viên: 10" in formatted
    assert "Đã check-in: 8" in formatted
    assert "Đi muộn: 2" in formatted


def test_excel_generation(setup_db):
    """Test Excel file generation."""
    excel_file = ExportService.generate_monthly_excel(2024, 1)
    
    assert isinstance(excel_file, BytesIO)
    assert excel_file.tell() == 0  # Position should be at start
    
    # Verify it's a valid Excel file
    from openpyxl import load_workbook
    wb = load_workbook(excel_file)
    
    assert "Tóm tắt" in wb.sheetnames
    assert "Chi tiết" in wb.sheetnames


def test_csv_generation(setup_db):
    """Test CSV generation."""
    csv_content = ExportService.generate_csv_report(2024, 1)
    
    assert "Họ tên" in csv_content
    assert "Giờ vào" in csv_content
    assert "User One" in csv_content
```

---

## Excel Report Sample Structure

### Sheet 1: Tóm tắt (Summary)

| STT | Họ và Tên | Số ngày đi làm | Số ngày muộn | Tổng phút muộn |
|-----|-----------|----------------|--------------|----------------|
| 1 | Nguyễn Văn A | 22 | 2 | 45 |
| 2 | Trần Thị B | 21 | 0 | 0 |
| 3 | Lê Văn C | 20 | 5 | 120 |

### Sheet 2: Chi tiết (Detail)

| Ngày | Nguyễn Văn A | | Trần Thị B | |
|------|--------------|------|------------|------|
| | Giờ vào | Giờ ra | Giờ vào | Giờ ra |
| 01/01 | 08:55 | 18:00 | 08:30 | 17:30 |
| 02/01 | **09:15** | 18:30 | 08:45 | 18:00 |
| 03/01 | - | - | 08:30 | 17:45 |

*Bold = late, - = absent*

---

## Verification Checklist

Before proceeding to the next blueprint, verify:

- [ ] `src/services/export.py` created with all methods
- [ ] `src/bot/handlers/report.py` created with handlers
- [ ] `/today` command shows daily summary
- [ ] `/export_excel` generates and sends Excel file
- [ ] Excel file has correct format and data
- [ ] Late arrivals are highlighted in Excel
- [ ] CSV export works correctly
- [ ] `/stats` shows overall statistics
- [ ] Optional: Google Sheets integration works

---

## Next Steps

Proceed to `08_ADMIN_COMMANDS.md` for the complete admin command reference.
