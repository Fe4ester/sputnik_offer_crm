"""Weekly report service."""

from datetime import date, datetime, timedelta

import pytz
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from sputnik_offer_crm.models import Student, WeeklyReport


class WeeklyReportService:
    """Service for student weekly report operations."""

    def __init__(self, session: AsyncSession):
        self.session = session

    def get_week_start_date(self, dt: datetime, timezone_str: str) -> date:
        """
        Get Monday of the week for given datetime in student's timezone.

        Args:
            dt: datetime to get week start for (typically now)
            timezone_str: student's timezone string (e.g., "Europe/Moscow")

        Returns:
            date: Monday of the week in student's local timezone
        """
        tz = pytz.timezone(timezone_str)
        local_dt = dt.astimezone(tz)
        # Get Monday of current week (weekday() returns 0 for Monday)
        days_since_monday = local_dt.weekday()
        monday = local_dt.date() - timedelta(days=days_since_monday)
        return monday

    async def can_submit_report(self, telegram_id: int) -> tuple[bool, str | None]:
        """
        Check if student can submit weekly report.

        Returns:
            tuple: (can_submit: bool, error_message: str | None)
        """
        # Get student
        result = await self.session.execute(
            select(Student).where(Student.telegram_id == telegram_id)
        )
        student = result.scalar_one_or_none()

        if not student:
            return False, "Студент не найден"

        if not student.is_eligible_for_notifications():
            if student.is_dropped():
                return False, "Ваш аккаунт неактивен. Обратитесь к ментору."
            elif student.is_on_pause():
                return False, "Вы на паузе. Обратитесь к ментору для возобновления."
            else:
                return False, "Ваш аккаунт неактивен. Обратитесь к ментору."

        # Get current week start in student's timezone
        now = datetime.now(pytz.UTC)
        week_start = self.get_week_start_date(now, student.timezone)

        # Check if report for this week already exists
        result = await self.session.execute(
            select(WeeklyReport).where(
                WeeklyReport.student_id == student.id,
                WeeklyReport.week_start_date == week_start,
            )
        )
        existing_report = result.scalar_one_or_none()

        if existing_report:
            return False, f"Вы уже отправили отчёт за эту неделю (с {week_start.strftime('%d.%m.%Y')})"

        return True, None

    async def submit_report(
        self,
        telegram_id: int,
        answer_what_did: str,
        answer_problems_solved: str | None,
        answer_problems_unsolved: str | None,
    ) -> WeeklyReport:
        """
        Submit weekly report for student.

        Args:
            telegram_id: student's telegram ID
            answer_what_did: answer to "what did you do"
            answer_problems_solved: answer to "problems solved" (optional)
            answer_problems_unsolved: answer to "problems unsolved" (optional)

        Returns:
            WeeklyReport: created report

        Raises:
            ValueError: if student not found or cannot submit
        """
        # Get student
        result = await self.session.execute(
            select(Student).where(Student.telegram_id == telegram_id)
        )
        student = result.scalar_one_or_none()

        if not student:
            raise ValueError("Студент не найден")

        # Get current week start
        now = datetime.now(pytz.UTC)
        week_start = self.get_week_start_date(now, student.timezone)

        # Double-check no existing report (race condition protection)
        result = await self.session.execute(
            select(WeeklyReport).where(
                WeeklyReport.student_id == student.id,
                WeeklyReport.week_start_date == week_start,
            )
        )
        existing_report = result.scalar_one_or_none()

        if existing_report:
            raise ValueError(f"Отчёт за эту неделю уже существует (с {week_start.strftime('%d.%m.%Y')})")

        # Create report
        report = WeeklyReport(
            student_id=student.id,
            week_start_date=week_start,
            answer_what_did=answer_what_did,
            answer_problems_solved=answer_problems_solved,
            answer_problems_unsolved=answer_problems_unsolved,
        )
        self.session.add(report)
        await self.session.flush()

        return report
