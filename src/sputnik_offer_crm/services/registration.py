"""Registration service."""

from datetime import datetime, timezone
from typing import NamedTuple

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from sputnik_offer_crm.models import (
    Direction,
    InviteCode,
    Stage,
    Student,
    StudentProgress,
)


class InviteCodeValidationError(Exception):
    """Base exception for invite code validation errors."""

    pass


class InviteCodeNotFoundError(InviteCodeValidationError):
    """Invite code not found."""

    pass


class InviteCodeAlreadyUsedError(InviteCodeValidationError):
    """Invite code already used."""

    pass


class DirectionHasNoStagesError(Exception):
    """Direction has no stages configured."""

    pass


class RegistrationResult(NamedTuple):
    """Result of successful registration."""

    student: Student
    direction: Direction
    first_stage: Stage


class RegistrationService:
    """Service for handling student registration flow."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def check_student_exists(self, telegram_id: int) -> Student | None:
        """Check if student with given telegram_id already exists."""
        result = await self.session.execute(
            select(Student).where(Student.telegram_id == telegram_id)
        )
        return result.scalar_one_or_none()

    async def validate_invite_code(self, code: str) -> InviteCode:
        """
        Validate invite code (non-locking check for initial validation).

        Raises:
            InviteCodeNotFoundError: Code not found
            InviteCodeAlreadyUsedError: Code already used
        """
        result = await self.session.execute(
            select(InviteCode).where(InviteCode.code == code)
        )
        invite_code = result.scalar_one_or_none()

        if not invite_code:
            raise InviteCodeNotFoundError(f"Код '{code}' не найден")

        if invite_code.used_at is not None:
            raise InviteCodeAlreadyUsedError(f"Код '{code}' уже использован")

        return invite_code

    async def validate_and_lock_invite_code(self, code: str) -> InviteCode:
        """
        Validate and lock invite code for exclusive use.

        Uses SELECT FOR UPDATE to prevent race conditions.
        Must be called within a transaction.

        Raises:
            InviteCodeNotFoundError: Code not found
            InviteCodeAlreadyUsedError: Code already used
        """
        result = await self.session.execute(
            select(InviteCode)
            .where(InviteCode.code == code)
            .with_for_update()
        )
        invite_code = result.scalar_one_or_none()

        if not invite_code:
            raise InviteCodeNotFoundError(f"Код '{code}' не найден")

        if invite_code.used_at is not None:
            raise InviteCodeAlreadyUsedError(f"Код '{code}' уже использован")

        return invite_code

    async def get_direction_first_stage(self, direction_id: int) -> Stage:
        """
        Get first stage of direction by stage_number.

        Raises:
            DirectionHasNoStagesError: Direction has no stages
        """
        result = await self.session.execute(
            select(Stage)
            .where(
                Stage.direction_id == direction_id,
                Stage.is_active == True,  # noqa: E712
            )
            .order_by(Stage.stage_number)
            .limit(1)
        )
        first_stage = result.scalar_one_or_none()

        if not first_stage:
            raise DirectionHasNoStagesError(
                f"Направление {direction_id} не имеет активных этапов"
            )

        return first_stage

    async def complete_registration(
        self,
        telegram_id: int,
        first_name: str,
        timezone_str: str,
        invite_code_str: str,
        last_name: str | None = None,
        username: str | None = None,
    ) -> RegistrationResult:
        """
        Complete student registration in a single transaction.

        Uses SELECT FOR UPDATE to prevent race conditions on invite code.

        Creates:
        - Student record
        - StudentProgress record
        - Marks invite code as used

        Raises:
            InviteCodeNotFoundError: Code not found
            InviteCodeAlreadyUsedError: Code already used (race condition)
            DirectionHasNoStagesError: Direction has no stages
        """
        # Lock invite code to prevent race conditions
        invite_code = await self.validate_and_lock_invite_code(invite_code_str)

        # Get direction
        result = await self.session.execute(
            select(Direction).where(Direction.id == invite_code.direction_id)
        )
        direction = result.scalar_one()

        # Get first stage
        first_stage = await self.get_direction_first_stage(direction.id)

        # Create student
        student = Student(
            telegram_id=telegram_id,
            first_name=first_name,
            last_name=last_name,
            username=username,
            timezone=timezone_str,
            is_active=True,
        )
        self.session.add(student)
        await self.session.flush()

        # Create progress
        progress = StudentProgress(
            student_id=student.id,
            direction_id=direction.id,
            current_stage_id=first_stage.id,
            started_at=datetime.now(timezone.utc),
        )
        self.session.add(progress)

        # Mark invite code as used
        invite_code.used_by_student_id = student.id
        invite_code.used_at = datetime.now(timezone.utc)

        await self.session.flush()

        return RegistrationResult(
            student=student,
            direction=direction,
            first_stage=first_stage,
        )
