"""Tests for WeeklyReportService."""

from datetime import datetime, timedelta

import pytest
import pytz
from freezegun import freeze_time

from sputnik_offer_crm.models import WeeklyReport
from sputnik_offer_crm.services import WeeklyReportService

pytest_plugins = ["tests.fixtures.db_fixtures"]


class TestWeeklyReportService:
    """Test weekly report service."""

    def test_get_week_start_date_monday(self):
        """Test get week start date when current day is Monday."""
        service = WeeklyReportService(None)  # type: ignore

        # Monday, May 11, 2026, 10:00 UTC
        dt = datetime(2026, 5, 11, 10, 0, 0, tzinfo=pytz.UTC)
        week_start = service.get_week_start_date(dt, "Europe/Moscow")

        # Should return the same Monday
        assert week_start.year == 2026
        assert week_start.month == 5
        assert week_start.day == 11

    def test_get_week_start_date_friday(self):
        """Test get week start date when current day is Friday."""
        service = WeeklyReportService(None)  # type: ignore

        # Friday, May 15, 2026, 10:00 UTC
        dt = datetime(2026, 5, 15, 10, 0, 0, tzinfo=pytz.UTC)
        week_start = service.get_week_start_date(dt, "Europe/Moscow")

        # Should return Monday of the same week (May 11)
        assert week_start.year == 2026
        assert week_start.month == 5
        assert week_start.day == 11

    def test_get_week_start_date_sunday(self):
        """Test get week start date when current day is Sunday."""
        service = WeeklyReportService(None)  # type: ignore

        # Sunday, May 17, 2026, 10:00 UTC
        dt = datetime(2026, 5, 17, 10, 0, 0, tzinfo=pytz.UTC)
        week_start = service.get_week_start_date(dt, "Europe/Moscow")

        # Should return Monday of the same week (May 11)
        assert week_start.year == 2026
        assert week_start.month == 5
        assert week_start.day == 11

    def test_get_week_start_date_different_timezone(self):
        """Test get week start date with different timezone."""
        service = WeeklyReportService(None)  # type: ignore

        # Sunday, May 17, 2026, 23:00 UTC (Monday May 18 in Tokyo)
        dt = datetime(2026, 5, 17, 23, 0, 0, tzinfo=pytz.UTC)
        week_start = service.get_week_start_date(dt, "Asia/Tokyo")

        # In Tokyo timezone, it's already Monday May 18
        # So week start should be May 18
        assert week_start.year == 2026
        assert week_start.month == 5
        assert week_start.day == 18

    @freeze_time("2026-05-15 10:00:00")
    async def test_can_submit_report_success(self, db_session, student):
        """Test can submit report when no report exists for current week."""
        service = WeeklyReportService(db_session)

        can_submit, error = await service.can_submit_report(student.telegram_id)

        assert can_submit is True
        assert error is None

    @freeze_time("2026-05-15 10:00:00")
    async def test_can_submit_report_already_submitted(self, db_session, student):
        """Test can submit report when report already exists for current week."""
        service = WeeklyReportService(db_session)

        # Create existing report for current week
        now = datetime.now(pytz.UTC)
        week_start = service.get_week_start_date(now, student.timezone)

        existing_report = WeeklyReport(
            student_id=student.id,
            week_start_date=week_start,
            answer_what_did="Test answer",
        )
        db_session.add(existing_report)
        await db_session.commit()

        can_submit, error = await service.can_submit_report(student.telegram_id)

        assert can_submit is False
        assert "уже отправили отчёт" in error

    async def test_can_submit_report_student_not_found(self, db_session):
        """Test can submit report when student not found."""
        service = WeeklyReportService(db_session)

        can_submit, error = await service.can_submit_report(999999999)

        assert can_submit is False
        assert error == "Студент не найден"

    async def test_can_submit_report_inactive_student(self, db_session, student):
        """Test can submit report when student is inactive."""
        service = WeeklyReportService(db_session)

        # Make student inactive (dropped)
        from sputnik_offer_crm.models import StudentStatus
        student.set_status(StudentStatus.DROPPED)
        await db_session.commit()

        can_submit, error = await service.can_submit_report(student.telegram_id)

        assert can_submit is False
        assert "неактивен" in error

    @freeze_time("2026-05-15 10:00:00")
    async def test_submit_report_success(self, db_session, student):
        """Test successful report submission."""
        service = WeeklyReportService(db_session)

        report = await service.submit_report(
            telegram_id=student.telegram_id,
            answer_what_did="I learned Python",
            answer_problems_solved="Fixed a bug",
            answer_problems_unsolved=None,
        )
        await db_session.commit()

        assert report.student_id == student.id
        assert report.answer_what_did == "I learned Python"
        assert report.answer_problems_solved == "Fixed a bug"
        assert report.answer_problems_unsolved is None
        assert report.week_start_date.weekday() == 0  # Monday

    @freeze_time("2026-05-15 10:00:00")
    async def test_submit_report_duplicate_protection(self, db_session, student):
        """Test that duplicate submission is prevented."""
        service = WeeklyReportService(db_session)

        # First submission
        await service.submit_report(
            telegram_id=student.telegram_id,
            answer_what_did="First report",
            answer_problems_solved=None,
            answer_problems_unsolved=None,
        )
        await db_session.commit()

        # Second submission should fail
        with pytest.raises(ValueError, match="уже существует"):
            await service.submit_report(
                telegram_id=student.telegram_id,
                answer_what_did="Second report",
                answer_problems_solved=None,
                answer_problems_unsolved=None,
            )

    async def test_submit_report_student_not_found(self, db_session):
        """Test submit report when student not found."""
        service = WeeklyReportService(db_session)

        with pytest.raises(ValueError, match="не найден"):
            await service.submit_report(
                telegram_id=999999999,
                answer_what_did="Test",
                answer_problems_solved=None,
                answer_problems_unsolved=None,
            )

    @freeze_time("2026-05-15 10:00:00")
    async def test_submit_report_all_answers(self, db_session, student):
        """Test submit report with all answers provided."""
        service = WeeklyReportService(db_session)

        report = await service.submit_report(
            telegram_id=student.telegram_id,
            answer_what_did="Learned async/await",
            answer_problems_solved="Fixed race condition",
            answer_problems_unsolved="Need help with deployment",
        )
        await db_session.commit()

        assert report.answer_what_did == "Learned async/await"
        assert report.answer_problems_solved == "Fixed race condition"
        assert report.answer_problems_unsolved == "Need help with deployment"

    @freeze_time("2026-05-11 10:00:00")  # Monday
    async def test_submit_report_different_weeks(self, db_session, student):
        """Test that reports can be submitted for different weeks."""
        service = WeeklyReportService(db_session)

        # Submit report for current week (May 11)
        report1 = await service.submit_report(
            telegram_id=student.telegram_id,
            answer_what_did="Week 1",
            answer_problems_solved=None,
            answer_problems_unsolved=None,
        )
        await db_session.commit()

        # Move to next week (May 18)
        with freeze_time("2026-05-18 10:00:00"):
            report2 = await service.submit_report(
                telegram_id=student.telegram_id,
                answer_what_did="Week 2",
                answer_problems_solved=None,
                answer_problems_unsolved=None,
            )
            await db_session.commit()

        assert report1.week_start_date.day == 11
        assert report2.week_start_date.day == 18
