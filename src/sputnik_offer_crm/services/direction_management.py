"""Service for managing directions and stages."""

from sqlalchemy import and_, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from sputnik_offer_crm.models import Direction, Stage, StudentProgress


class DirectionManagementError(Exception):
    """Base exception for direction management errors."""


class DirectionCodeAlreadyExistsError(DirectionManagementError):
    """Direction with this code already exists."""


class DirectionNotFoundError(DirectionManagementError):
    """Direction not found."""


class DirectionInUseError(DirectionManagementError):
    """Direction is in use and cannot be deactivated."""


class DirectionStageNotFoundError(DirectionManagementError):
    """Stage not found."""


class DirectionStageInUseError(DirectionManagementError):
    """Stage is in use and cannot be deactivated."""


class InvalidDurationError(DirectionManagementError):
    """Invalid planned duration value."""


class DirectionManagementService:
    """Service for direction and stage management."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def list_directions(self) -> list[Direction]:
        """
        Get all directions ordered by name.

        Returns:
            List of all directions (active and inactive)
        """
        result = await self.session.execute(
            select(Direction).order_by(Direction.name)
        )
        return list(result.scalars().all())

    async def create_direction(self, code: str, name: str) -> Direction:
        """
        Create new direction.

        Args:
            code: unique direction code (e.g., "python", "frontend")
            name: human-readable name

        Returns:
            Created direction

        Raises:
            DirectionCodeAlreadyExistsError: if code already exists
        """
        direction = Direction(
            code=code.strip().lower(),
            name=name.strip(),
            is_active=True,
        )
        self.session.add(direction)

        try:
            await self.session.flush()
        except IntegrityError as e:
            await self.session.rollback()
            if "unique" in str(e).lower() or "code" in str(e).lower():
                raise DirectionCodeAlreadyExistsError(
                    f"Направление с кодом '{code}' уже существует"
                ) from e
            raise

        await self.session.refresh(direction)
        return direction

    async def deactivate_direction(self, direction_id: int) -> Direction:
        """
        Deactivate direction.

        Args:
            direction_id: direction ID

        Returns:
            Updated direction

        Raises:
            DirectionNotFoundError: if direction not found
            DirectionInUseError: if direction has active students
        """
        result = await self.session.execute(
            select(Direction).where(Direction.id == direction_id)
        )
        direction = result.scalar_one_or_none()

        if not direction:
            raise DirectionNotFoundError(f"Направление с ID {direction_id} не найдено")

        if direction.is_active:
            active_students_count = await self._count_active_students_in_direction(
                direction_id
            )
            if active_students_count > 0:
                raise DirectionInUseError(
                    f"Направление используется {active_students_count} активными студентами"
                )

            direction.is_active = False
            await self.session.flush()

        await self.session.refresh(direction)
        return direction

    async def get_direction_stages(self, direction_id: int) -> list[Stage]:
        """
        Get all stages for direction ordered by stage_number.

        Args:
            direction_id: direction ID

        Returns:
            List of stages

        Raises:
            DirectionNotFoundError: if direction not found
        """
        result = await self.session.execute(
            select(Direction).where(Direction.id == direction_id)
        )
        direction = result.scalar_one_or_none()

        if not direction:
            raise DirectionNotFoundError(f"Направление с ID {direction_id} не найдено")

        stages_result = await self.session.execute(
            select(Stage)
            .where(Stage.direction_id == direction_id)
            .order_by(Stage.stage_number)
        )
        return list(stages_result.scalars().all())

    async def create_stage(
        self,
        direction_id: int,
        title: str,
        description: str | None = None,
        planned_duration_days: int | None = None,
    ) -> Stage:
        """
        Create new stage in direction.

        Stage number is auto-assigned as max(stage_number) + 1.

        Args:
            direction_id: direction ID
            title: stage title
            description: optional description
            planned_duration_days: optional planned duration

        Returns:
            Created stage

        Raises:
            DirectionNotFoundError: if direction not found
        """
        result = await self.session.execute(
            select(Direction).where(Direction.id == direction_id)
        )
        direction = result.scalar_one_or_none()

        if not direction:
            raise DirectionNotFoundError(f"Направление с ID {direction_id} не найдено")

        max_stage_number_result = await self.session.execute(
            select(func.max(Stage.stage_number)).where(
                Stage.direction_id == direction_id
            )
        )
        max_stage_number = max_stage_number_result.scalar()
        next_stage_number = (max_stage_number or 0) + 1

        stage = Stage(
            direction_id=direction_id,
            stage_number=next_stage_number,
            title=title.strip(),
            description=description.strip() if description else None,
            planned_duration_days=planned_duration_days,
            is_active=True,
        )
        self.session.add(stage)
        await self.session.flush()
        await self.session.refresh(stage)
        return stage

    async def deactivate_stage(self, stage_id: int) -> Stage:
        """
        Deactivate stage.

        Args:
            stage_id: stage ID

        Returns:
            Updated stage

        Raises:
            DirectionStageNotFoundError: if stage not found
            DirectionStageInUseError: if stage is current stage for active students
        """
        result = await self.session.execute(select(Stage).where(Stage.id == stage_id))
        stage = result.scalar_one_or_none()

        if not stage:
            raise DirectionStageNotFoundError(f"Этап с ID {stage_id} не найден")

        if stage.is_active:
            active_students_count = await self._count_active_students_on_stage(stage_id)
            if active_students_count > 0:
                raise DirectionStageInUseError(
                    f"Этап является текущим для {active_students_count} активных студентов"
                )

            stage.is_active = False
            await self.session.flush()

        await self.session.refresh(stage)
        return stage

    async def _count_active_students_in_direction(self, direction_id: int) -> int:
        """Count active students in direction."""
        from sputnik_offer_crm.models import Student

        result = await self.session.execute(
            select(func.count(StudentProgress.id))
            .join(Student, Student.id == StudentProgress.student_id)
            .where(
                and_(
                    StudentProgress.direction_id == direction_id,
                    Student.is_active == True,  # noqa: E712
                )
            )
        )
        return result.scalar() or 0

    async def _count_active_students_on_stage(self, stage_id: int) -> int:
        """Count active students on this stage."""
        from sputnik_offer_crm.models import Student

        result = await self.session.execute(
            select(func.count(StudentProgress.id))
            .join(Student, Student.id == StudentProgress.student_id)
            .where(
                and_(
                    StudentProgress.current_stage_id == stage_id,
                    Student.is_active == True,  # noqa: E712
                )
            )
        )
        return result.scalar() or 0

    async def update_direction(
        self,
        direction_id: int,
        name: str | None = None,
    ) -> Direction:
        """
        Update direction fields.

        Args:
            direction_id: direction ID
            name: new name (if provided)

        Returns:
            Updated direction

        Raises:
            DirectionNotFoundError: if direction not found

        Note:
            Code is intentionally not editable to avoid breaking dependencies.
        """
        result = await self.session.execute(
            select(Direction).where(Direction.id == direction_id)
        )
        direction = result.scalar_one_or_none()

        if not direction:
            raise DirectionNotFoundError(f"Направление с ID {direction_id} не найдено")

        if name is not None:
            direction.name = name.strip()

        await self.session.flush()
        await self.session.refresh(direction)
        return direction

    async def update_stage(
        self,
        stage_id: int,
        title: str | None = None,
        description: str | None = None,
        planned_duration_days: int | None = None,
        clear_description: bool = False,
        clear_duration: bool = False,
    ) -> Stage:
        """
        Update stage fields.

        Args:
            stage_id: stage ID
            title: new title (if provided)
            description: new description (if provided)
            planned_duration_days: new duration (if provided)
            clear_description: if True, clear description field
            clear_duration: if True, clear planned_duration_days field

        Returns:
            Updated stage

        Raises:
            DirectionStageNotFoundError: if stage not found
            InvalidDurationError: if duration is invalid

        Note:
            stage_number is intentionally not editable to avoid breaking stage order.
        """
        result = await self.session.execute(select(Stage).where(Stage.id == stage_id))
        stage = result.scalar_one_or_none()

        if not stage:
            raise DirectionStageNotFoundError(f"Этап с ID {stage_id} не найден")

        if title is not None:
            stage.title = title.strip()

        if clear_description:
            stage.description = None
        elif description is not None:
            stage.description = description.strip() if description.strip() else None

        if clear_duration:
            stage.planned_duration_days = None
        elif planned_duration_days is not None:
            if planned_duration_days <= 0:
                raise InvalidDurationError(
                    "Длительность должна быть положительным числом"
                )
            stage.planned_duration_days = planned_duration_days

        await self.session.flush()
        await self.session.refresh(stage)
        return stage
