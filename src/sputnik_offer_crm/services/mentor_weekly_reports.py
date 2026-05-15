"""Mentor weekly reports service."""

from datetime import date
from typing import NamedTuple

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from sputnik_offer_crm.models import Student, WeeklyReport


class ReportSummary(NamedTuple):
    """Weekly report summary for list view."""

    id: int
    week_start_date: date
    student_name: str
    has_problems_unsolved: bool


class ReportDetail(NamedTuple):
    """Full weekly report details."""

    id: int
    week_start_date: date
    student_name: str
    answer_what_did: str
    answer_problems_solved: str | None
    answer_problems_unsolved: str | None


class MentorReportsError(Exception):
    """Base error for mentor reports operations."""


class StudentNotFoundError(MentorReportsError):
    """Student not found."""


class ReportNotFoundError(MentorReportsError):
    """Report not found."""


class MentorWeeklyReportsService:
    """Service for mentor weekly reports operations."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_student_reports(
        self, student_id: int, limit: int = 10
    ) -> list[ReportSummary]:
        """
        Get weekly reports for student.

        Args:
            student_id: student ID
            limit: maximum number of reports to return

        Returns:
            List of ReportSummary ordered by week_start_date desc

        Raises:
            StudentNotFoundError: if student not found
        """
        # Verify student exists
        result = await self.session.execute(
            select(Student).where(Student.id == student_id)
        )
        student = result.scalar_one_or_none()

        if not student:
            raise StudentNotFoundError(f"Student {student_id} not found")

        # Get reports
        result = await self.session.execute(
            select(WeeklyReport)
            .where(WeeklyReport.student_id == student_id)
            .order_by(WeeklyReport.week_start_date.desc())
            .limit(limit)
        )
        reports = result.scalars().all()

        student_name = student.first_name
        if student.last_name:
            student_name += f" {student.last_name}"

        return [
            ReportSummary(
                id=report.id,
                week_start_date=report.week_start_date,
                student_name=student_name,
                has_problems_unsolved=bool(report.answer_problems_unsolved),
            )
            for report in reports
        ]

    async def get_report_detail(self, report_id: int) -> ReportDetail:
        """
        Get full report details.

        Args:
            report_id: report ID

        Returns:
            ReportDetail with full report content

        Raises:
            ReportNotFoundError: if report not found
        """
        # Get report with student
        result = await self.session.execute(
            select(WeeklyReport, Student)
            .join(Student, Student.id == WeeklyReport.student_id)
            .where(WeeklyReport.id == report_id)
        )
        row = result.one_or_none()

        if not row:
            raise ReportNotFoundError(f"Report {report_id} not found")

        report, student = row

        student_name = student.first_name
        if student.last_name:
            student_name += f" {student.last_name}"

        return ReportDetail(
            id=report.id,
            week_start_date=report.week_start_date,
            student_name=student_name,
            answer_what_did=report.answer_what_did,
            answer_problems_solved=report.answer_problems_solved,
            answer_problems_unsolved=report.answer_problems_unsolved,
        )

    async def get_recent_reports(self, limit: int = 20) -> list[ReportSummary]:
        """
        Get recent reports across all students.

        Args:
            limit: maximum number of reports to return

        Returns:
            List of ReportSummary ordered by week_start_date desc
        """
        result = await self.session.execute(
            select(WeeklyReport, Student)
            .join(Student, Student.id == WeeklyReport.student_id)
            .order_by(WeeklyReport.week_start_date.desc())
            .limit(limit)
        )
        rows = result.all()

        summaries = []
        for report, student in rows:
            student_name = student.first_name
            if student.last_name:
                student_name += f" {student.last_name}"

            summaries.append(
                ReportSummary(
                    id=report.id,
                    week_start_date=report.week_start_date,
                    student_name=student_name,
                    has_problems_unsolved=bool(report.answer_problems_unsolved),
                )
            )

        return summaries
