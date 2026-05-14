"""Tests for DirectionManagementService."""

from datetime import datetime

import pytest
import pytz
from sqlalchemy.ext.asyncio import AsyncSession

from sputnik_offer_crm.models import Direction, Stage, Student, StudentProgress
from sputnik_offer_crm.services.direction_management import (
    DirectionCodeAlreadyExistsError,
    DirectionInUseError,
    DirectionManagementService,
    DirectionNotFoundError,
    DirectionStageInUseError,
    DirectionStageNotFoundError,
)


@pytest.fixture
def service(db_session: AsyncSession) -> DirectionManagementService:
    """Create service instance."""
    return DirectionManagementService(db_session)


@pytest.fixture
async def direction(db_session: AsyncSession) -> Direction:
    """Create test direction."""
    direction = Direction(code="python", name="Python Backend", is_active=True)
    db_session.add(direction)
    await db_session.commit()
    await db_session.refresh(direction)
    return direction


@pytest.fixture
async def inactive_direction(db_session: AsyncSession) -> Direction:
    """Create inactive direction."""
    direction = Direction(code="old", name="Old Direction", is_active=False)
    db_session.add(direction)
    await db_session.commit()
    await db_session.refresh(direction)
    return direction


@pytest.fixture
async def stage(db_session: AsyncSession, direction: Direction) -> Stage:
    """Create test stage."""
    stage = Stage(
        direction_id=direction.id,
        stage_number=1,
        title="Stage 1",
        description="First stage",
        planned_duration_days=14,
        is_active=True,
    )
    db_session.add(stage)
    await db_session.commit()
    await db_session.refresh(stage)
    return stage


@pytest.mark.asyncio
async def test_list_directions_empty(service: DirectionManagementService) -> None:
    """Test listing directions when none exist."""
    directions = await service.list_directions()
    assert len(directions) == 0


@pytest.mark.asyncio
async def test_list_directions(
    service: DirectionManagementService,
    direction: Direction,
    inactive_direction: Direction,
) -> None:
    """Test listing all directions."""
    directions = await service.list_directions()

    assert len(directions) == 2
    codes = [d.code for d in directions]
    assert "python" in codes
    assert "old" in codes


@pytest.mark.asyncio
async def test_create_direction(service: DirectionManagementService) -> None:
    """Test creating new direction."""
    direction = await service.create_direction(code="frontend", name="Frontend Development")

    assert direction.id is not None
    assert direction.code == "frontend"
    assert direction.name == "Frontend Development"
    assert direction.is_active is True


@pytest.mark.asyncio
async def test_create_direction_normalizes_code(
    service: DirectionManagementService,
) -> None:
    """Test that direction code is normalized to lowercase."""
    direction = await service.create_direction(code="  PyThOn  ", name="Python")

    assert direction.code == "python"


@pytest.mark.asyncio
async def test_create_direction_duplicate_code(
    service: DirectionManagementService,
    direction: Direction,
) -> None:
    """Test creating direction with duplicate code fails."""
    with pytest.raises(DirectionCodeAlreadyExistsError) as exc_info:
        await service.create_direction(code="python", name="Another Python")

    assert "python" in str(exc_info.value)


@pytest.mark.asyncio
async def test_deactivate_direction(
    service: DirectionManagementService,
    direction: Direction,
) -> None:
    """Test deactivating direction."""
    updated = await service.deactivate_direction(direction.id)

    assert updated.id == direction.id
    assert updated.is_active is False


@pytest.mark.asyncio
async def test_deactivate_direction_not_found(
    service: DirectionManagementService,
) -> None:
    """Test deactivating non-existent direction."""
    with pytest.raises(DirectionNotFoundError):
        await service.deactivate_direction(99999)


@pytest.mark.asyncio
async def test_deactivate_direction_with_active_students(
    service: DirectionManagementService,
    direction: Direction,
    stage: Stage,
    db_session: AsyncSession,
) -> None:
    """Test that direction with active students cannot be deactivated."""
    student = Student(
        telegram_id=123456789,
        first_name="Test",
        last_name="Student",
        username="teststudent",
        timezone="Europe/Moscow",
        is_active=True,
    )
    db_session.add(student)
    await db_session.flush()

    progress = StudentProgress(
        student_id=student.id,
        direction_id=direction.id,
        current_stage_id=stage.id,
        started_at=datetime.now(pytz.UTC),
    )
    db_session.add(progress)
    await db_session.commit()

    with pytest.raises(DirectionInUseError) as exc_info:
        await service.deactivate_direction(direction.id)

    assert "активными студентами" in str(exc_info.value)


@pytest.mark.asyncio
async def test_deactivate_direction_already_inactive(
    service: DirectionManagementService,
    inactive_direction: Direction,
) -> None:
    """Test deactivating already inactive direction is idempotent."""
    updated = await service.deactivate_direction(inactive_direction.id)

    assert updated.is_active is False


@pytest.mark.asyncio
async def test_get_direction_stages_empty(
    service: DirectionManagementService,
    direction: Direction,
) -> None:
    """Test getting stages for direction with no stages."""
    stages = await service.get_direction_stages(direction.id)

    assert len(stages) == 0


@pytest.mark.asyncio
async def test_get_direction_stages(
    service: DirectionManagementService,
    direction: Direction,
    stage: Stage,
    db_session: AsyncSession,
) -> None:
    """Test getting stages for direction."""
    stage2 = Stage(
        direction_id=direction.id,
        stage_number=2,
        title="Stage 2",
        is_active=True,
    )
    db_session.add(stage2)
    await db_session.commit()

    stages = await service.get_direction_stages(direction.id)

    assert len(stages) == 2
    assert stages[0].stage_number == 1
    assert stages[1].stage_number == 2


@pytest.mark.asyncio
async def test_get_direction_stages_not_found(
    service: DirectionManagementService,
) -> None:
    """Test getting stages for non-existent direction."""
    with pytest.raises(DirectionNotFoundError):
        await service.get_direction_stages(99999)


@pytest.mark.asyncio
async def test_create_stage(
    service: DirectionManagementService,
    direction: Direction,
) -> None:
    """Test creating new stage."""
    stage = await service.create_stage(
        direction_id=direction.id,
        title="First Stage",
        description="Description",
        planned_duration_days=14,
    )

    assert stage.id is not None
    assert stage.direction_id == direction.id
    assert stage.stage_number == 1
    assert stage.title == "First Stage"
    assert stage.description == "Description"
    assert stage.planned_duration_days == 14
    assert stage.is_active is True


@pytest.mark.asyncio
async def test_create_stage_auto_increment_number(
    service: DirectionManagementService,
    direction: Direction,
    stage: Stage,
) -> None:
    """Test that stage number is auto-incremented."""
    stage2 = await service.create_stage(
        direction_id=direction.id,
        title="Second Stage",
    )

    assert stage2.stage_number == 2


@pytest.mark.asyncio
async def test_create_stage_direction_not_found(
    service: DirectionManagementService,
) -> None:
    """Test creating stage for non-existent direction."""
    with pytest.raises(DirectionNotFoundError):
        await service.create_stage(
            direction_id=99999,
            title="Stage",
        )


@pytest.mark.asyncio
async def test_create_stage_optional_fields(
    service: DirectionManagementService,
    direction: Direction,
) -> None:
    """Test creating stage with only required fields."""
    stage = await service.create_stage(
        direction_id=direction.id,
        title="Minimal Stage",
    )

    assert stage.description is None
    assert stage.planned_duration_days is None


@pytest.mark.asyncio
async def test_deactivate_stage(
    service: DirectionManagementService,
    stage: Stage,
) -> None:
    """Test deactivating stage."""
    updated = await service.deactivate_stage(stage.id)

    assert updated.id == stage.id
    assert updated.is_active is False


@pytest.mark.asyncio
async def test_deactivate_stage_not_found(
    service: DirectionManagementService,
) -> None:
    """Test deactivating non-existent stage."""
    with pytest.raises(DirectionStageNotFoundError):
        await service.deactivate_stage(99999)


@pytest.mark.asyncio
async def test_deactivate_stage_with_active_students(
    service: DirectionManagementService,
    direction: Direction,
    stage: Stage,
    db_session: AsyncSession,
) -> None:
    """Test that stage with active students cannot be deactivated."""
    student = Student(
        telegram_id=123456789,
        first_name="Test",
        last_name="Student",
        username="teststudent",
        timezone="Europe/Moscow",
        is_active=True,
    )
    db_session.add(student)
    await db_session.flush()

    progress = StudentProgress(
        student_id=student.id,
        direction_id=direction.id,
        current_stage_id=stage.id,
        started_at=datetime.now(pytz.UTC),
    )
    db_session.add(progress)
    await db_session.commit()

    with pytest.raises(DirectionStageInUseError) as exc_info:
        await service.deactivate_stage(stage.id)

    assert "активных студентов" in str(exc_info.value)


@pytest.mark.asyncio
async def test_deactivate_stage_already_inactive(
    service: DirectionManagementService,
    db_session: AsyncSession,
    direction: Direction,
) -> None:
    """Test deactivating already inactive stage is idempotent."""
    stage = Stage(
        direction_id=direction.id,
        stage_number=1,
        title="Inactive Stage",
        is_active=False,
    )
    db_session.add(stage)
    await db_session.commit()
    await db_session.refresh(stage)

    updated = await service.deactivate_stage(stage.id)

    assert updated.is_active is False
