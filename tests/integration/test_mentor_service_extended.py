"""Additional tests for MentorService."""

import pytest

from sputnik_offer_crm.services import MentorNotFoundError, MentorService

pytest_plugins = ["tests.fixtures.db_fixtures"]


class TestMentorServiceExtended:
    """Extended tests for mentor service."""

    async def test_check_mentor_access_success(self, db_session, mentor):
        """Test check mentor access for active mentor."""
        service = MentorService(db_session)

        result = await service.check_mentor_access(mentor.telegram_id)

        assert result.id == mentor.id
        assert result.is_active is True

    async def test_check_mentor_access_not_found(self, db_session):
        """Test check mentor access for non-existent mentor."""
        service = MentorService(db_session)

        with pytest.raises(MentorNotFoundError):
            await service.check_mentor_access(999999999)

    async def test_check_mentor_access_inactive(self, db_session, mentor):
        """Test check mentor access for inactive mentor."""
        mentor.is_active = False
        await db_session.commit()

        service = MentorService(db_session)

        with pytest.raises(MentorNotFoundError):
            await service.check_mentor_access(mentor.telegram_id)

    async def test_get_active_directions_multiple(self, db_session, direction):
        """Test get active directions with multiple directions."""
        from sputnik_offer_crm.models import Direction

        # Create second direction
        direction2 = Direction(
            code="frontend",
            name="Frontend Development",
            is_active=True,
        )
        db_session.add(direction2)
        await db_session.commit()

        service = MentorService(db_session)

        directions = await service.get_active_directions()

        assert len(directions) == 2
        assert all(d.is_active for d in directions)

    async def test_generate_invite_code_excludes_ambiguous_chars(self, db_session):
        """Test that generated codes exclude ambiguous characters."""
        service = MentorService(db_session)

        # Generate many codes to test character set
        codes = [service.generate_invite_code() for _ in range(100)]

        for code in codes:
            assert "O" not in code
            assert "0" not in code
            assert "I" not in code
            assert "1" not in code
            assert code.isupper()
            assert code.isalnum()

    async def test_generate_invite_code_custom_length(self, db_session):
        """Test generate invite code with custom length."""
        service = MentorService(db_session)

        code_6 = service.generate_invite_code(length=6)
        code_10 = service.generate_invite_code(length=10)
        code_15 = service.generate_invite_code(length=15)

        assert len(code_6) == 6
        assert len(code_10) == 10
        assert len(code_15) == 15
