"""Export service for Telegram Attendance Bot.

Provides functionality to generate daily reports, monthly Excel exports, and CSV reports.
"""

from __future__ import annotations

import csv
import io
from calendar import monthrange
from dataclasses import dataclass, field
from datetime import date, datetime, time, timedelta
from typing import Dict, List, Optional, Tuple

import pytz
from openpyxl import Workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter
from sqlalchemy import and_, func

from src.config import get_config
from src.database import (
    AttendanceLog,
    AttendanceType,
    User,
    UserStatus,
    get_db_session,
)


@dataclass
class DailyReportData:
    """Data class for daily attendance report."""

    date: date
    total_employees: int
    checked_in: int
    on_time: int
    late: int
    not_checked_in: int
    checked_out: int
    present_users: List[Tuple[str, datetime, bool]]  # (name, check_in_time, is_late)
    absent_users: List[str]
    late_users: List[Tuple[str, datetime, int]]  # (name, check_in_time, late_minutes)


@dataclass
class EmployeeMonthlyData:
    """Data class for individual employee monthly attendance data."""

    user_id: int
    full_name: str
    daily_records: Dict[int, Tuple[Optional[datetime], Optional[datetime], bool]]  # day -> (in, out, is_late)
    total_days_present: int = 0
    late_days: int = 0
    total_late_minutes: int = 0


@dataclass
class MonthlyReportData:
    """Data class for monthly attendance report."""

    year: int
    month: int
    employee_data: List[EmployeeMonthlyData] = field(default_factory=list)
    summary: Dict[str, int] = field(default_factory=dict)


class ExportService:
    """Service for exporting attendance data to various formats."""

    # Excel styles as class variables
    HEADER_FILL = PatternFill(start_color="4472C4", end_color="4472C4", fill_type="solid")
    HEADER_FONT = Font(color="FFFFFF", bold=True)
    LATE_FILL = PatternFill(start_color="FF6B6B", end_color="FF6B6B", fill_type="solid")
    ABSENT_FILL = PatternFill(start_color="FFE66D", end_color="FFE66D", fill_type="solid")
    THIN_BORDER = Border(
        left=Side(style="thin"),
        right=Side(style="thin"),
        top=Side(style="thin"),
        bottom=Side(style="thin"),
    )

    @staticmethod
    def get_daily_report(target_date: Optional[date] = None) -> DailyReportData:
        """
        Get daily attendance report data.

        Args:
            target_date: The date to generate the report for. Defaults to today.

        Returns:
            DailyReportData containing attendance statistics for the day.
        """
        config = get_config()
        tz = pytz.timezone(config.timezone.timezone)

        if target_date is None:
            target_date = datetime.now(tz).date()

        # Define the day boundaries in local timezone
        day_start = tz.localize(datetime.combine(target_date, time.min))
        day_end = tz.localize(datetime.combine(target_date, time.max))

        # Work start time for late calculation
        work_start = tz.localize(
            datetime.combine(
                target_date,
                time(config.attendance.work_start_hour, config.attendance.work_start_minute),
            )
        )
        late_threshold = work_start + timedelta(minutes=config.attendance.late_threshold_minutes)

        with get_db_session() as session:
            # Get all active employees
            active_users = (
                session.query(User)
                .filter(User.status == UserStatus.ACTIVE)
                .all()
            )
            total_employees = len(active_users)
            user_map = {user.user_id: user.full_name for user in active_users}

            # Get all check-ins for the day
            check_ins = (
                session.query(AttendanceLog)
                .filter(
                    and_(
                        AttendanceLog.type == AttendanceType.IN,
                        AttendanceLog.timestamp >= day_start,
                        AttendanceLog.timestamp <= day_end,
                    )
                )
                .all()
            )

            # Get all check-outs for the day
            check_outs = (
                session.query(AttendanceLog)
                .filter(
                    and_(
                        AttendanceLog.type == AttendanceType.OUT,
                        AttendanceLog.timestamp >= day_start,
                        AttendanceLog.timestamp <= day_end,
                    )
                )
                .all()
            )

            # Build check-in data (earliest check-in per user)
            user_check_ins: Dict[int, AttendanceLog] = {}
            for log in check_ins:
                if log.user_id not in user_check_ins or log.timestamp < user_check_ins[log.user_id].timestamp:
                    user_check_ins[log.user_id] = log

            # Build check-out data (latest check-out per user)
            user_check_outs: Dict[int, AttendanceLog] = {}
            for log in check_outs:
                if log.user_id not in user_check_outs or log.timestamp > user_check_outs[log.user_id].timestamp:
                    user_check_outs[log.user_id] = log

            # Calculate statistics
            checked_in = len(user_check_ins)
            checked_out = len(user_check_outs)

            present_users: List[Tuple[str, datetime, bool]] = []
            late_users: List[Tuple[str, datetime, int]] = []
            on_time = 0
            late = 0

            for user_id, log in user_check_ins.items():
                user_name = user_map.get(user_id, f"User {user_id}")
                check_in_time = log.timestamp
                is_late = log.is_late or check_in_time > late_threshold

                present_users.append((user_name, check_in_time, is_late))

                if is_late:
                    late += 1
                    late_minutes = int((check_in_time - work_start).total_seconds() / 60)
                    late_users.append((user_name, check_in_time, max(0, late_minutes)))
                else:
                    on_time += 1

            # Calculate absent users
            checked_in_user_ids = set(user_check_ins.keys())
            absent_users = [
                user_map[user_id]
                for user_id in user_map.keys()
                if user_id not in checked_in_user_ids
            ]
            not_checked_in = len(absent_users)

            # Sort lists
            present_users.sort(key=lambda x: x[1])  # Sort by check-in time
            late_users.sort(key=lambda x: x[2], reverse=True)  # Sort by late minutes descending
            absent_users.sort()

            return DailyReportData(
                date=target_date,
                total_employees=total_employees,
                checked_in=checked_in,
                on_time=on_time,
                late=late,
                not_checked_in=not_checked_in,
                checked_out=checked_out,
                present_users=present_users,
                absent_users=absent_users,
                late_users=late_users,
            )

    @staticmethod
    def format_daily_report(report: DailyReportData) -> str:
        """
        Format daily report data as a text string for Telegram message.

        Args:
            report: DailyReportData to format.

        Returns:
            Formatted string suitable for Telegram message.
        """
        config = get_config()
        tz = pytz.timezone(config.timezone.timezone)

        lines = [
            f"BÁO CÁO CHẤM CÔNG NGÀY {report.date.strftime('%d/%m/%Y')}",
            "=" * 40,
            "",
            "TỔNG QUAN:",
            f"  Tổng nhân viên: {report.total_employees}",
            f"  Đã check-in: {report.checked_in}",
            f"  Đúng giờ: {report.on_time}",
            f"  Đi muộn: {report.late}",
            f"  Chưa check-in: {report.not_checked_in}",
            f"  Đã check-out: {report.checked_out}",
            "",
        ]

        if report.late_users:
            lines.append("NHÂN VIÊN ĐI MUỘN:")
            for name, check_in_time, late_minutes in report.late_users:
                local_time = check_in_time.astimezone(tz) if check_in_time.tzinfo else tz.localize(check_in_time)
                lines.append(f"  - {name}: {local_time.strftime('%H:%M')} (muộn {late_minutes} phút)")
            lines.append("")

        if report.absent_users:
            lines.append("CHƯA CHECK-IN:")
            for name in report.absent_users:
                lines.append(f"  - {name}")
            lines.append("")

        if report.present_users:
            lines.append("ĐÃ CHECK-IN:")
            for name, check_in_time, is_late in report.present_users:
                local_time = check_in_time.astimezone(tz) if check_in_time.tzinfo else tz.localize(check_in_time)
                status = " (muộn)" if is_late else ""
                lines.append(f"  - {name}: {local_time.strftime('%H:%M')}{status}")

        return "\n".join(lines)

    @staticmethod
    def _get_monthly_data(year: int, month: int) -> MonthlyReportData:
        """
        Get monthly attendance data for all employees.

        Args:
            year: The year to generate the report for.
            month: The month to generate the report for.

        Returns:
            MonthlyReportData containing attendance data for the month.
        """
        config = get_config()
        tz = pytz.timezone(config.timezone.timezone)

        # Get the number of days in the month
        _, num_days = monthrange(year, month)

        # Define month boundaries
        month_start = tz.localize(datetime(year, month, 1, 0, 0, 0))
        if month == 12:
            month_end = tz.localize(datetime(year + 1, 1, 1, 0, 0, 0)) - timedelta(seconds=1)
        else:
            month_end = tz.localize(datetime(year, month + 1, 1, 0, 0, 0)) - timedelta(seconds=1)

        # Work start time for late calculation
        work_start_time = time(config.attendance.work_start_hour, config.attendance.work_start_minute)

        with get_db_session() as session:
            # Get all active employees
            active_users = (
                session.query(User)
                .filter(User.status == UserStatus.ACTIVE)
                .order_by(User.full_name)
                .all()
            )

            # Get all attendance logs for the month
            logs = (
                session.query(AttendanceLog)
                .filter(
                    and_(
                        AttendanceLog.timestamp >= month_start,
                        AttendanceLog.timestamp <= month_end,
                    )
                )
                .order_by(AttendanceLog.timestamp)
                .all()
            )

            # Organize logs by user and day
            user_logs: Dict[int, Dict[int, Dict[str, List[AttendanceLog]]]] = {}
            for log in logs:
                user_id = log.user_id
                local_time = log.timestamp.astimezone(tz) if log.timestamp.tzinfo else tz.localize(log.timestamp)
                day = local_time.day
                log_type = log.type.value if isinstance(log.type, AttendanceType) else log.type

                if user_id not in user_logs:
                    user_logs[user_id] = {}
                if day not in user_logs[user_id]:
                    user_logs[user_id][day] = {"IN": [], "OUT": []}
                user_logs[user_id][day][log_type].append(log)

            # Build employee data
            employee_data: List[EmployeeMonthlyData] = []
            total_present = 0
            total_late = 0

            for user in active_users:
                emp_data = EmployeeMonthlyData(
                    user_id=user.user_id,
                    full_name=user.full_name,
                    daily_records={},
                )

                user_day_logs = user_logs.get(user.user_id, {})

                for day in range(1, num_days + 1):
                    day_logs = user_day_logs.get(day, {"IN": [], "OUT": []})

                    # Get earliest check-in
                    check_in: Optional[datetime] = None
                    is_late = False
                    if day_logs["IN"]:
                        earliest_in = min(day_logs["IN"], key=lambda x: x.timestamp)
                        check_in = earliest_in.timestamp
                        is_late = earliest_in.is_late

                        # Also calculate late based on work start time
                        local_check_in = check_in.astimezone(tz) if check_in.tzinfo else tz.localize(check_in)
                        work_start_dt = tz.localize(datetime.combine(date(year, month, day), work_start_time))
                        late_threshold = work_start_dt + timedelta(minutes=config.attendance.late_threshold_minutes)

                        if local_check_in > late_threshold:
                            is_late = True
                            late_minutes = int((local_check_in - work_start_dt).total_seconds() / 60)
                            emp_data.total_late_minutes += max(0, late_minutes)

                    # Get latest check-out
                    check_out: Optional[datetime] = None
                    if day_logs["OUT"]:
                        latest_out = max(day_logs["OUT"], key=lambda x: x.timestamp)
                        check_out = latest_out.timestamp

                    emp_data.daily_records[day] = (check_in, check_out, is_late)

                    if check_in:
                        emp_data.total_days_present += 1
                        if is_late:
                            emp_data.late_days += 1

                total_present += emp_data.total_days_present
                total_late += emp_data.late_days
                employee_data.append(emp_data)

            summary = {
                "total_employees": len(active_users),
                "total_working_days": num_days,
                "total_present": total_present,
                "total_late": total_late,
            }

            return MonthlyReportData(
                year=year,
                month=month,
                employee_data=employee_data,
                summary=summary,
            )

    @staticmethod
    def generate_monthly_excel(year: int, month: int) -> io.BytesIO:
        """
        Generate monthly Excel report with summary and detail sheets.

        Args:
            year: The year to generate the report for.
            month: The month to generate the report for.

        Returns:
            BytesIO containing the Excel workbook.
        """
        config = get_config()
        tz = pytz.timezone(config.timezone.timezone)
        _, num_days = monthrange(year, month)

        # Get monthly data
        report_data = ExportService._get_monthly_data(year, month)

        # Create workbook
        wb = Workbook()

        # ============ Sheet 1: Summary (Tóm tắt) ============
        ws_summary = wb.active
        ws_summary.title = "Tóm tắt"

        # Title
        ws_summary.merge_cells("A1:E1")
        ws_summary["A1"] = f"BÁO CÁO CHẤM CÔNG THÁNG {month:02d}/{year}"
        ws_summary["A1"].font = Font(bold=True, size=14)
        ws_summary["A1"].alignment = Alignment(horizontal="center")

        # Headers
        headers = ["STT", "Họ và tên", "Số ngày làm việc", "Số ngày đi muộn", "Tổng phút đi muộn"]
        for col, header in enumerate(headers, 1):
            cell = ws_summary.cell(row=3, column=col, value=header)
            cell.fill = ExportService.HEADER_FILL
            cell.font = ExportService.HEADER_FONT
            cell.border = ExportService.THIN_BORDER
            cell.alignment = Alignment(horizontal="center")

        # Data rows
        for idx, emp in enumerate(report_data.employee_data, 1):
            row = idx + 3
            ws_summary.cell(row=row, column=1, value=idx).border = ExportService.THIN_BORDER
            ws_summary.cell(row=row, column=2, value=emp.full_name).border = ExportService.THIN_BORDER
            ws_summary.cell(row=row, column=3, value=emp.total_days_present).border = ExportService.THIN_BORDER
            
            late_cell = ws_summary.cell(row=row, column=4, value=emp.late_days)
            late_cell.border = ExportService.THIN_BORDER
            if emp.late_days > 0:
                late_cell.fill = ExportService.LATE_FILL

            minutes_cell = ws_summary.cell(row=row, column=5, value=emp.total_late_minutes)
            minutes_cell.border = ExportService.THIN_BORDER
            if emp.total_late_minutes > 0:
                minutes_cell.fill = ExportService.LATE_FILL

        # Adjust column widths
        ws_summary.column_dimensions["A"].width = 6
        ws_summary.column_dimensions["B"].width = 25
        ws_summary.column_dimensions["C"].width = 18
        ws_summary.column_dimensions["D"].width = 18
        ws_summary.column_dimensions["E"].width = 18

        # ============ Sheet 2: Detail (Chi tiết) ============
        ws_detail = wb.create_sheet("Chi tiết")

        # Title
        title_end_col = len(report_data.employee_data) * 2 + 1
        ws_detail.merge_cells(start_row=1, start_column=1, end_row=1, end_column=max(title_end_col, 5))
        ws_detail["A1"] = f"CHI TIẾT CHẤM CÔNG THÁNG {month:02d}/{year}"
        ws_detail["A1"].font = Font(bold=True, size=14)
        ws_detail["A1"].alignment = Alignment(horizontal="center")

        # Column headers - Date column + Employee columns (2 sub-columns each: In/Out)
        ws_detail.cell(row=3, column=1, value="Ngày").fill = ExportService.HEADER_FILL
        ws_detail.cell(row=3, column=1).font = ExportService.HEADER_FONT
        ws_detail.cell(row=3, column=1).border = ExportService.THIN_BORDER
        ws_detail.cell(row=3, column=1).alignment = Alignment(horizontal="center")

        col = 2
        for emp in report_data.employee_data:
            # Merge cells for employee name
            ws_detail.merge_cells(start_row=2, start_column=col, end_row=2, end_column=col + 1)
            name_cell = ws_detail.cell(row=2, column=col, value=emp.full_name)
            name_cell.fill = ExportService.HEADER_FILL
            name_cell.font = ExportService.HEADER_FONT
            name_cell.border = ExportService.THIN_BORDER
            name_cell.alignment = Alignment(horizontal="center")

            # In/Out sub-headers
            in_cell = ws_detail.cell(row=3, column=col, value="Vào")
            in_cell.fill = ExportService.HEADER_FILL
            in_cell.font = ExportService.HEADER_FONT
            in_cell.border = ExportService.THIN_BORDER
            in_cell.alignment = Alignment(horizontal="center")

            out_cell = ws_detail.cell(row=3, column=col + 1, value="Ra")
            out_cell.fill = ExportService.HEADER_FILL
            out_cell.font = ExportService.HEADER_FONT
            out_cell.border = ExportService.THIN_BORDER
            out_cell.alignment = Alignment(horizontal="center")

            col += 2

        # Data rows - one row per day
        for day in range(1, num_days + 1):
            row = day + 3
            current_date = date(year, month, day)

            # Date column
            date_cell = ws_detail.cell(row=row, column=1, value=current_date.strftime("%d/%m"))
            date_cell.border = ExportService.THIN_BORDER
            date_cell.alignment = Alignment(horizontal="center")

            # Employee data
            col = 2
            for emp in report_data.employee_data:
                check_in, check_out, is_late = emp.daily_records.get(day, (None, None, False))

                # Check-in time
                in_value = ""
                if check_in:
                    local_in = check_in.astimezone(tz) if check_in.tzinfo else tz.localize(check_in)
                    in_value = local_in.strftime("%H:%M")

                in_cell = ws_detail.cell(row=row, column=col, value=in_value)
                in_cell.border = ExportService.THIN_BORDER
                in_cell.alignment = Alignment(horizontal="center")
                
                if is_late and check_in:
                    in_cell.fill = ExportService.LATE_FILL
                elif not check_in:
                    in_cell.fill = ExportService.ABSENT_FILL

                # Check-out time
                out_value = ""
                if check_out:
                    local_out = check_out.astimezone(tz) if check_out.tzinfo else tz.localize(check_out)
                    out_value = local_out.strftime("%H:%M")

                out_cell = ws_detail.cell(row=row, column=col + 1, value=out_value)
                out_cell.border = ExportService.THIN_BORDER
                out_cell.alignment = Alignment(horizontal="center")
                
                if not check_out and check_in:
                    out_cell.fill = ExportService.ABSENT_FILL

                col += 2

        # Adjust column widths for detail sheet
        ws_detail.column_dimensions["A"].width = 10
        for col_idx in range(2, len(report_data.employee_data) * 2 + 2):
            ws_detail.column_dimensions[get_column_letter(col_idx)].width = 8

        # Save to BytesIO
        output = io.BytesIO()
        wb.save(output)
        output.seek(0)

        return output

    @staticmethod
    def generate_csv_report(year: int, month: int) -> str:
        """
        Generate monthly CSV report.

        Args:
            year: The year to generate the report for.
            month: The month to generate the report for.

        Returns:
            CSV string containing the monthly attendance data.
        """
        config = get_config()
        tz = pytz.timezone(config.timezone.timezone)
        _, num_days = monthrange(year, month)

        # Get monthly data
        report_data = ExportService._get_monthly_data(year, month)

        # Create CSV in memory
        output = io.StringIO()
        writer = csv.writer(output)

        # Header row 1: Title
        writer.writerow([f"Báo cáo chấm công tháng {month:02d}/{year}"])
        writer.writerow([])

        # Header row 2: Column headers
        headers = ["Ngày"]
        for emp in report_data.employee_data:
            headers.extend([f"{emp.full_name} - Vào", f"{emp.full_name} - Ra"])
        writer.writerow(headers)

        # Data rows
        for day in range(1, num_days + 1):
            current_date = date(year, month, day)
            row = [current_date.strftime("%d/%m/%Y")]

            for emp in report_data.employee_data:
                check_in, check_out, is_late = emp.daily_records.get(day, (None, None, False))

                # Check-in time
                if check_in:
                    local_in = check_in.astimezone(tz) if check_in.tzinfo else tz.localize(check_in)
                    in_value = local_in.strftime("%H:%M")
                    if is_late:
                        in_value += " (muộn)"
                else:
                    in_value = ""

                # Check-out time
                if check_out:
                    local_out = check_out.astimezone(tz) if check_out.tzinfo else tz.localize(check_out)
                    out_value = local_out.strftime("%H:%M")
                else:
                    out_value = ""

                row.extend([in_value, out_value])

            writer.writerow(row)

        # Summary section
        writer.writerow([])
        writer.writerow(["TÓM TẮT"])
        writer.writerow(["STT", "Họ và tên", "Số ngày làm việc", "Số ngày đi muộn", "Tổng phút đi muộn"])
        for idx, emp in enumerate(report_data.employee_data, 1):
            writer.writerow([
                idx,
                emp.full_name,
                emp.total_days_present,
                emp.late_days,
                emp.total_late_minutes,
            ])

        return output.getvalue()
