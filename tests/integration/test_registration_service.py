"""Tests for RegistrationService."""

from datetime import datetime, timezone

import pytest

from sputnik_offer_crm.models import InviteCode, Student, StudentProgress
from sputnik_offer_crm.services import (
    DirectionHasNoStagesError,
    InviteCodeAlreadyUsedError,
    InviteCodeNotFoundError,
    RegistrationService,
)

# Import fixtures
pytest_plugins = ["tests.fixtures.db_fixtures"]


class TestRegistrationService:
    """Test registration service."""

    async def test_validate_invite_code_success(self, db_session, invite_code):
        """Test successful invite code validation."""
        service = RegistrationService(db_session)

        result = await service.validate_invite_code(invite_code.code)

        assert result == invite_code
        assert not result.used_at

    async def test_validate_invite_code_not_found(self, db_session):
        """Test invite code not found."""
        service = RegistrationService(db_session)

        with pytest.raises(InviteCodeNotFoundError):
            await service.validate_invite_code("NOTEXIST")

    async def test_validate_invite_code_already_used(self, db_session, used_invite_code):
        """Test invite code already used."""
        service = RegistrationService(db_session)

        with pytest.raises(InviteCodeAlreadyUsedError):
            await service.validate_invite_code(used_invite_code.code)

    async def test_check_student_exists_true(self, db_session, student):
        """Test check student exists returns student."""
        service = RegistrationService(db_session)

        result = await service.check_student_exists(student.telegram_id)

        assert result is not None
        assert result.id == student.id

    async def test_check_student_exists_false(self, db_session):
        """Test check student exists returns None."""
        service = RegistrationService(db_session)

        result = await service.check_student_exists(999999999)

        assert result is None

    async def test_complete_registration_success(
        self, db_session, invite_code, direction, direction_stage
    ):
        """Test successful registration."""
        service = RegistrationService(db_session)

        result = await service.complete_registration(
            telegram_id=111222333,
            first_name="Тест",
            last_name="Тестов",
            username="test_user",
            timezone_str="Europe/Moscow",
            invite_code_str=invite_code.code,
        )

        assert result.student.telegram_id == 111222333
        assert result.student.first_name == "Тест"
        assert result.student.timezone == "Europe/Moscow"
        assert result.direction.id == direction.id
        assert result.first_stage.id == direction_stage.id

        # Check invite code marked as used
        await db_session.refresh(invite_code)
        assert invite_code.used_at is not None
        assert invite_code.used_by_student_id is not None

    async def test_complete_registration_code_not_found(self, db_session):
        """Test registration with non-existent code."""
        service = RegistrationService(db_session)

        with pytest.raises(InviteCodeNotFoundError):
            await service.complete_registration(
                telegram_id=111222333,
                first_name="Тест",
                last_name="Тестов",
                username="test_user",
                timezone_str="Europe/Moscow",
                invite_code_str="NOTEXIST",
            )

    async def test_complete_registration_code_already_used(
        self, db_session, used_invite_code
    ):
        """Test registration with already used code."""
        service = RegistrationService(db_session)

        with pytest.raises(InviteCodeAlreadyUsedError):
            await service.complete_registration(
                telegram_id=111222333,
                first_name="Тест",
                last_name="Тестов",
                username="test_user",
                timezone_str="Europe/Moscow",
                invite_code_str=used_invite_code.code,
            )

    async def test_complete_registration_direction_no_stages(
        self, db_session, invite_code
    ):
        """Test registration when direction has no stages."""
        service = RegistrationService(db_session)

        # Direction exists but has no stages
        with pytest.raises(DirectionHasNoStagesError):
            await service.complete_registration(
                telegram_id=111222333,
                first_name="Тест",
                last_name="Тестов",
                username="test_user",
                timezone_str="Europe/Moscow",
                invite_code_str=invite_code.code,
            )

    async def test_complete_registration_without_last_name(
        self, db_session, invite_code, direction_stage
    ):
        """Test registration without last name."""
        service = RegistrationService(db_session)

        result = await service.complete_registration(
            telegram_id=111222333,
            first_name="Тест",
            last_name=None,
            username="test_user",
            timezone_str="Europe/Moscow",
            invite_code_str=invite_code.code,
        )

        assert result.student.last_name is None

    async def test_complete_registration_without_username(
        self, db_session, invite_code, direction_stage
    ):
        """Test registration without username."""
        service = RegistrationService(db_session)

        result = await service.complete_registration(
            telegram_id=111222333,
            first_name="Тест",
            last_name="Тестов",
            username=None,
            timezone_str="Europe/Moscow",
            invite_code_str=invite_code.code,
        )

        assert result.student.username is None
