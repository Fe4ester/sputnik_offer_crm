"""Tests for MentorStudentService."""

import pytest

from sputnik_offer_crm.services import MentorStudentService

pytest_plugins = ["tests.fixtures.db_fixtures"]


class TestMentorStudentService:
    """Test mentor student service."""

    async def test_search_students_by_username(self, db_session, student):
        """Test search students by username."""
        service = MentorStudentService(db_session)

        results = await service.search_students(student.username)

        assert len(results) == 1
        assert results[0].student.id == student.id

    async def test_search_students_by_username_with_at(self, db_session, student):
        """Test search students by username with @ prefix."""
        service = MentorStudentService(db_session)

        results = await service.search_students(f"@{student.username}")

        assert len(results) == 1
        assert results[0].student.id == student.id

    async def test_search_students_by_first_name(self, db_session, student):
        """Test search students by first name."""
        service = MentorStudentService(db_session)

        results = await service.search_students(student.first_name)

        assert len(results) == 1
        assert results[0].student.id == student.id

    async def test_search_students_by_last_name(self, db_session, student):
        """Test search students by last name."""
        service = MentorStudentService(db_session)

        results = await service.search_students(student.last_name)

        assert len(results) == 1
        assert results[0].student.id == student.id

    async def test_search_students_by_telegram_id(self, db_session, student):
        """Test search students by telegram_id."""
        service = MentorStudentService(db_session)

        results = await service.search_students(str(student.telegram_id))

        assert len(results) == 1
        assert results[0].student.id == student.id

    async def test_search_students_partial_match(self, db_session, student):
        """Test search students with partial name match."""
        service = MentorStudentService(db_session)

        # Search by first 3 characters of first name
        partial = student.first_name[:3]
        results = await service.search_students(partial)

        assert len(results) >= 1
        assert any(r.student.id == student.id for r in results)

    async def test_search_students_no_results(self, db_session):
        """Test search students with no results."""
        service = MentorStudentService(db_session)

        results = await service.search_students("nonexistent_user_12345")

        assert len(results) == 0

    async def test_search_students_with_direction(
        self, db_session, student, direction, student_progress
    ):
        """Test search students includes direction name."""
        service = MentorStudentService(db_session)

        results = await service.search_students(student.username)

        assert len(results) == 1
        assert results[0].direction_name == direction.name

    async def test_search_students_without_progress(self, db_session, student):
        """Test search students without progress (no direction)."""
        service = MentorStudentService(db_session)

        results = await service.search_students(student.username)

        assert len(results) == 1
        assert results[0].direction_name is None

    async def test_get_student_card_success(
        self, db_session, student, direction, stage, student_progress
    ):
        """Test get student card with all data."""
        service = MentorStudentService(db_session)

        card = await service.get_student_card(student.id)

        assert card is not None
        assert card.student.id == student.id
        assert card.direction.id == direction.id
        assert card.current_stage.id == stage.id
        assert card.progress.id == student_progress.id
        assert isinstance(card.deadlines, list)
        assert isinstance(card.recent_reports, list)

    async def test_get_student_card_not_found(self, db_session):
        """Test get student card for non-existent student."""
        service = MentorStudentService(db_session)

        card = await service.get_student_card(999999)

        assert card is None

    async def test_get_student_card_no_progress(self, db_session, student):
        """Test get student card for student without progress."""
        service = MentorStudentService(db_session)

        card = await service.get_student_card(student.id)

        assert card is None

    async def test_get_student_card_with_deadlines(
        self, db_session, student, direction, stage, student_progress, student_stage_progress, student_task
    ):
        """Test get student card includes deadlines."""
        service = MentorStudentService(db_session)

        card = await service.get_student_card(student.id)

        assert card is not None
        assert len(card.deadlines) == 2  # stage deadline + task deadline

    async def test_get_student_card_with_weekly_reports(
        self, db_session, student, direction, stage, student_progress, weekly_report
    ):
        """Test get student card includes weekly reports."""
        service = MentorStudentService(db_session)

        card = await service.get_student_card(student.id)

        assert card is not None
        assert len(card.recent_reports) == 1
        assert card.recent_reports[0].id == weekly_report.id

    async def test_get_student_card_limits_reports_to_three(
        self, db_session, student, direction, stage, student_progress
    ):
        """Test get student card limits weekly reports to 3."""
        from datetime import date
        from sputnik_offer_crm.models import WeeklyReport

        # Create 5 reports with valid dates
        dates = [
            date(2026, 4, 20),  # Week 1
            date(2026, 4, 27),  # Week 2
            date(2026, 5, 4),   # Week 3
            date(2026, 5, 11),  # Week 4
            date(2026, 5, 18),  # Week 5
        ]
        for i, report_date in enumerate(dates):
            report = WeeklyReport(
                student_id=student.id,
                week_start_date=report_date,
                answer_what_did=f"Report {i}",
            )
            db_session.add(report)
        await db_session.commit()

        service = MentorStudentService(db_session)
        card = await service.get_student_card(student.id)

        assert card is not None
        assert len(card.recent_reports) == 3  # Limited to 3
