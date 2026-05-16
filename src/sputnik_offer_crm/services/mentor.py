"""Mentor service."""

import secrets
import string
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from sputnik_offer_crm.models import Direction, InviteCode, Mentor


class MentorNotFoundError(Exception):
    """Mentor not found."""

    pass


class MentorAdminRequiredError(Exception):
    """Mentor admin access required."""

    pass


class NoActiveDirectionsError(Exception):
    """No active directions available."""

    pass


class InviteCodeGenerationError(Exception):
    """Failed to generate unique invite code."""

    pass


class MentorService:
    """Service for mentor operations."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_mentor(self, telegram_id: int) -> Mentor | None:
        """Get mentor by telegram_id."""
        result = await self.session.execute(
            select(Mentor).where(Mentor.telegram_id == telegram_id)
        )
        return result.scalar_one_or_none()

    async def check_mentor_access(self, telegram_id: int) -> Mentor:
        """
        Check if user has mentor access.

        Raises:
            MentorNotFoundError: User is not a mentor
        """
        mentor = await self.get_mentor(telegram_id)
        if not mentor or not mentor.is_active:
            raise MentorNotFoundError("Доступ запрещён")
        return mentor

    async def check_mentor_admin_access(self, telegram_id: int) -> Mentor:
        """Check if user has active mentor admin access."""
        mentor = await self.check_mentor_access(telegram_id)
        if not mentor.is_admin:
            raise MentorAdminRequiredError("Доступ запрещён")
        return mentor

    async def get_active_directions(self) -> list[Direction]:
        """Get list of active directions."""
        result = await self.session.execute(
            select(Direction)
            .where(Direction.is_active == True)  # noqa: E712
            .order_by(Direction.name)
        )
        return list(result.scalars().all())

    def generate_invite_code(self, length: int = 8) -> str:
        """
        Generate random invite code.

        Uses alphanumeric characters excluding ambiguous ones:
        - Excludes: O, 0, I, l, 1
        - Includes: uppercase letters and digits

        Args:
            length: Code length (default 8)

        Returns:
            Generated code string
        """
        # Exclude ambiguous characters
        alphabet = string.ascii_uppercase.replace("O", "").replace("I", "") + string.digits.replace("0", "").replace("1", "")
        # Result: ABCDEFGHJKLMNPQRSTUVWXYZ23456789
        return "".join(secrets.choice(alphabet) for _ in range(length))

    async def create_invite_code(
        self,
        mentor_id: int,
        direction_id: int,
        suggested_timezone: str | None = None,
        max_attempts: int = 5,
    ) -> InviteCode:
        """
        Create invite code with unique code generation.

        Args:
            mentor_id: Mentor ID
            direction_id: Direction ID
            suggested_timezone: Optional suggested timezone
            max_attempts: Maximum attempts to generate unique code

        Returns:
            Created InviteCode

        Raises:
            InviteCodeGenerationError: Failed to generate unique code
        """
        for attempt in range(max_attempts):
            code = self.generate_invite_code()

            invite_code = InviteCode(
                code=code,
                mentor_id=mentor_id,
                direction_id=direction_id,
                suggested_timezone=suggested_timezone,
                created_at=datetime.now(timezone.utc),
            )

            self.session.add(invite_code)

            try:
                await self.session.flush()
                return invite_code
            except IntegrityError:
                # Code collision, try again
                await self.session.rollback()
                continue

        raise InviteCodeGenerationError(
            f"Failed to generate unique invite code after {max_attempts} attempts"
        )
