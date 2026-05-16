"""Tests for direction and stage editing."""

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from sputnik_offer_crm.models import Direction, Stage
from sputnik_offer_crm.services.direction_management import (
    DirectionManagementService,
    DirectionNotFoundError,
    DirectionStageNotFoundError,
    InvalidDurationError,
)


@pytest.fixture
def service(db_session: AsyncSession) -> DirectionManagementService:
    """Create service instance."""
    return DirectionManagementService(db_session)


@pytest.fixture
async def direction(db_session: AsyncSession) -> Direction:
    """Create test direction."""
    direction = Direction(
        code="test",
        name="Test Direction",
        is_active=True,
    )
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
        title="Test Stage",
        description="Test description",
        planned_duration_days=30,
        is_active=True,
    )
    db_session.add(stage)
    await db_session.commit()
    await db_session.refresh(stage)
    return stage


@pytest.mark.asyncio
async def test_update_direction_name(
    service: DirectionManagementService,
    direction: Direction,
) -> None:
    """Test updating direction name."""
    updated = await service.update_direction(
        direction_id=direction.id,
        name="Updated Direction Name",
    )

    assert updated.id == direction.id
    assert updated.name == "Updated Direction Name"
    assert updated.code == "test"  # Code unchanged


@pytest.mark.asyncio
async def test_update_direction_strips_whitespace(
    service: DirectionManagementService,
    direction: Direction,
) -> None:
    """Test that update strips whitespace."""
    updated = await service.update_direction(
        direction_id=direction.id,
        name="  Spaced Name  ",
    )

    assert updated.name == "Spaced Name"


@pytest.mark.asyncio
async def test_update_direction_not_found(
    service: DirectionManagementService,
) -> None:
    """Test updating non-existent direction."""
    with pytest.raises(DirectionNotFoundError):
        await service.update_direction(
            direction_id=99999,
            name="New Name",
        )


@pytest.mark.asyncio
async def test_update_direction_no_changes(
    service: DirectionManagementService,
    direction: Direction,
) -> None:
    """Test updating direction with no changes."""
    updated = await service.update_direction(direction_id=direction.id)

    assert updated.id == direction.id
    assert updated.name == direction.name


@pytest.mark.asyncio
async def test_update_stage_title(
    service: DirectionManagementService,
    stage: Stage,
) -> None:
    """Test updating stage title."""
    updated = await service.update_stage(
        stage_id=stage.id,
        title="Updated Stage Title",
    )

    assert updated.id == stage.id
    assert updated.title == "Updated Stage Title"
    assert updated.description == "Test description"
    assert updated.planned_duration_days == 30


@pytest.mark.asyncio
async def test_update_stage_description(
    service: DirectionManagementService,
    stage: Stage,
) -> None:
    """Test updating stage description."""
    updated = await service.update_stage(
        stage_id=stage.id,
        description="New description",
    )

    assert updated.description == "New description"


@pytest.mark.asyncio
async def test_update_stage_clear_description(
    service: DirectionManagementService,
    stage: Stage,
) -> None:
    """Test clearing stage description."""
    updated = await service.update_stage(
        stage_id=stage.id,
        clear_description=True,
    )

    assert updated.description is None


@pytest.mark.asyncio
async def test_update_stage_duration(
    service: DirectionManagementService,
    stage: Stage,
) -> None:
    """Test updating stage duration."""
    updated = await service.update_stage(
        stage_id=stage.id,
        planned_duration_days=60,
    )

    assert updated.planned_duration_days == 60


@pytest.mark.asyncio
async def test_update_stage_clear_duration(
    service: DirectionManagementService,
    stage: Stage,
) -> None:
    """Test clearing stage duration."""
    updated = await service.update_stage(
        stage_id=stage.id,
        clear_duration=True,
    )

    assert updated.planned_duration_days is None


@pytest.mark.asyncio
async def test_update_stage_invalid_duration(
    service: DirectionManagementService,
    stage: Stage,
) -> None:
    """Test updating stage with invalid duration."""
    with pytest.raises(InvalidDurationError):
        await service.update_stage(
            stage_id=stage.id,
            planned_duration_days=0,
        )

    with pytest.raises(InvalidDurationError):
        await service.update_stage(
            stage_id=stage.id,
            planned_duration_days=-10,
        )


@pytest.mark.asyncio
async def test_update_stage_not_found(
    service: DirectionManagementService,
) -> None:
    """Test updating non-existent stage."""
    with pytest.raises(DirectionStageNotFoundError):
        await service.update_stage(
            stage_id=99999,
            title="New Title",
        )


@pytest.mark.asyncio
async def test_update_stage_multiple_fields(
    service: DirectionManagementService,
    stage: Stage,
) -> None:
    """Test updating multiple stage fields at once."""
    updated = await service.update_stage(
        stage_id=stage.id,
        title="New Title",
        description="New Description",
        planned_duration_days=45,
    )

    assert updated.title == "New Title"
    assert updated.description == "New Description"
    assert updated.planned_duration_days == 45


@pytest.mark.asyncio
async def test_update_stage_strips_whitespace(
    service: DirectionManagementService,
    stage: Stage,
) -> None:
    """Test that update strips whitespace."""
    updated = await service.update_stage(
        stage_id=stage.id,
        title="  Spaced Title  ",
        description="  Spaced Description  ",
    )

    assert updated.title == "Spaced Title"
    assert updated.description == "Spaced Description"


@pytest.mark.asyncio
async def test_update_stage_empty_description_becomes_none(
    service: DirectionManagementService,
    stage: Stage,
) -> None:
    """Test that empty description becomes None."""
    updated = await service.update_stage(
        stage_id=stage.id,
        description="   ",
    )

    assert updated.description is None


@pytest.mark.asyncio
async def test_update_stage_no_changes(
    service: DirectionManagementService,
    stage: Stage,
) -> None:
    """Test updating stage with no changes."""
    updated = await service.update_stage(stage_id=stage.id)

    assert updated.id == stage.id
    assert updated.title == stage.title
    assert updated.description == stage.description
    assert updated.planned_duration_days == stage.planned_duration_days
