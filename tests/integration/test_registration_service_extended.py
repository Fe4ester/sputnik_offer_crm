"""Additional tests for RegistrationService edge cases."""

import pytest
from sqlalchemy import select

from sputnik_offer_crm.models import InviteCode, Student, StudentProgress
from sputnik_offer_crm.services import (
    DirectionHasNoStagesError,
    InviteCodeAlreadyUsedError,
    InviteCodeNotFoundError,
    RegistrationService,
)

pytest_plugins = ["tests.fixtures.db_fixtures"]


class TestRegistrationServiceEdgeCases:
    """Test registration service edge cases."""

    async def test_validate_and_lock_invite_code_success(self, db_session, invite_code):
        """Test validate and lock invite code."""
        service = RegistrationService(db_session)

        result = await service.validate_and_lock_invite_code(invite_code.code)

        assert result == invite_code
        assert result.used_at is None

    async def test_validate_and_lock_invite_code_not_found(self, db_session):
        """Test validate and lock with non-existent code."""
        service = RegistrationService(db_session)

        with pytest.raises(InviteCodeNotFoundError):
            await service.validate_and_lock_invite_code("NOTEXIST")

    async def test_validate_and_lock_invite_code_already_used(self, db_session, used_invite_code):
        """Test validate and lock with already used code."""
        service = RegistrationService(db_session)

        with pytest.raises(InviteCodeAlreadyUsedError):
            await service.validate_and_lock_invite_code(used_invite_code.code)

    async def test_get_direction_first_stage_success(self, db_session, direction, direction_stage):
        """Test get direction first stage."""
        service = RegistrationService(db_session)

        result = await service.get_direction_first_stage(direction.id)

        assert result.id == direction_stage.id
        assert result.order_index == 0

    async def test_get_direction_first_stage_no_stages(self, db_session, direction):
        """Test get direction first stage when no stages exist."""
        service = RegistrationService(db_session)

        with pytest.raises(DirectionHasNoStagesError):
            await service.get_direction_first_stage(direction.id)

    async def test_complete_registration_creates_all_entities(
        self, db_session, invite_code, direction, direction_stage
    ):
        """Test that complete registration creates student and progress."""
        service = RegistrationService(db_session)

        result = await service.complete_registration(
            telegram_id=999888777,
            first_name="Новый",
            last_name="Студент",
            username="new_student",
            timezone_str="Asia/Tokyo",
            invite_code_str=invite_code.code,
        )

        # Verify student created
        student_result = await db_session.execute(
            select(Student).where(Student.telegram_id == 999888777)
        )
        student = student_result.scalar_one()
        assert student.first_name == "Новый"
        assert student.timezone == "Asia/Tokyo"

        # Verify progress created
        progress_result = await db_session.execute(
            select(StudentProgress).where(StudentProgress.student_id == student.id)
        )
        progress = progress_result.scalar_one()
        assert progress.direction_id == direction.id
        assert progress.current_stage_id == direction_stage.id

        # Verify invite code marked as used
        await db_session.refresh(invite_code)
        assert invite_code.used_at is not None
        assert invite_code.used_by_student_id == student.id
