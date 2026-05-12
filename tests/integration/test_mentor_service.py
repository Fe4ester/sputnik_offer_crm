"""Tests for MentorService."""

import pytest
from sqlalchemy import select

from sputnik_offer_crm.models import InviteCode
from sputnik_offer_crm.services import (
    InviteCodeGenerationError,
    MentorNotFoundError,
    MentorService,
    NoActiveDirectionsError,
)

pytest_plugins = ["tests.fixtures.db_fixtures"]


class TestMentorService:
    """Test mentor service."""

    async def test_get_mentor_success(self, db_session, mentor):
        """Test get mentor by telegram_id."""
        service = MentorService(db_session)

        result = await service.get_mentor(mentor.telegram_id)

        assert result is not None
        assert result.id == mentor.id
        assert result.telegram_id == mentor.telegram_id

    async def test_get_mentor_not_found(self, db_session):
        """Test get mentor returns None when not found."""
        service = MentorService(db_session)

        result = await service.get_mentor(999999999)

        assert result is None

    async def test_get_active_directions(self, db_session, direction):
        """Test get active directions."""
        service = MentorService(db_session)

        directions = await service.get_active_directions()

        assert len(directions) == 1
        assert directions[0].id == direction.id
        assert directions[0].is_active is True

    async def test_get_active_directions_empty(self, db_session, direction):
        """Test get active directions when all inactive."""
        direction.is_active = False
        await db_session.commit()

        service = MentorService(db_session)

        directions = await service.get_active_directions()

        assert len(directions) == 0

    async def test_generate_invite_code_format(self, db_session):
        """Test invite code generation format."""
        service = MentorService(db_session)

        code = service.generate_invite_code(length=8)

        assert len(code) == 8
        assert code.isupper()
        assert code.isalnum()
        # Should not contain confusing characters
        assert "O" not in code
        assert "I" not in code
        assert "0" not in code
        assert "1" not in code

    async def test_generate_invite_code_different_lengths(self, db_session):
        """Test invite code generation with different lengths."""
        service = MentorService(db_session)

        code_6 = service.generate_invite_code(length=6)
        code_12 = service.generate_invite_code(length=12)

        assert len(code_6) == 6
        assert len(code_12) == 12

    async def test_create_invite_code_success(self, db_session, mentor, direction):
        """Test successful invite code creation."""
        service = MentorService(db_session)

        code = await service.create_invite_code(
            mentor_id=mentor.id,
            direction_id=direction.id,
            suggested_timezone="Europe/Moscow",
        )

        assert code is not None
        assert len(code.code) == 8
        assert code.mentor_id == mentor.id
        assert code.direction_id == direction.id
        assert code.suggested_timezone == "Europe/Moscow"
        assert code.used_at is None

    async def test_create_invite_code_uniqueness(self, db_session, mentor, direction):
        """Test that generated codes are unique."""
        service = MentorService(db_session)

        code1 = await service.create_invite_code(
            mentor_id=mentor.id,
            direction_id=direction.id,
            suggested_timezone="Europe/Moscow",
        )

        code2 = await service.create_invite_code(
            mentor_id=mentor.id,
            direction_id=direction.id,
            suggested_timezone="Europe/Moscow",
        )

        assert code1.code != code2.code

    async def test_create_invite_code_retry_on_collision(self, db_session, mentor, direction, monkeypatch):
        """Test retry logic when code collision occurs."""
        service = MentorService(db_session)

        # Create first code
        first_code = await service.create_invite_code(
            mentor_id=mentor.id,
            direction_id=direction.id,
            suggested_timezone="Europe/Moscow",
        )

        # Mock generate_invite_code to return existing code first, then new code
        call_count = 0
        original_generate = service.generate_invite_code

        def mock_generate(length=8):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return first_code.code  # Return existing code
            return original_generate(length)

        monkeypatch.setattr(service, "generate_invite_code", mock_generate)

        # Should retry and succeed
        second_code = await service.create_invite_code(
            mentor_id=mentor.id,
            direction_id=direction.id,
            suggested_timezone="Europe/Moscow",
        )

        assert second_code.code != first_code.code
        assert call_count == 2
