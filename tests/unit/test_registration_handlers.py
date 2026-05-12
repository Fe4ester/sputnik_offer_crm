"""Tests for registration handlers."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, User

from sputnik_offer_crm.bot.handlers.registration import (
    cmd_start,
    handle_invite_code_input,
    process_invite_code,
)
from sputnik_offer_crm.bot.states import RegistrationStates
from sputnik_offer_crm.services import InviteCodeAlreadyUsedError, InviteCodeNotFoundError

pytest_plugins = ["tests.fixtures.db_fixtures"]


@pytest.fixture
def mock_message():
    """Create mock message."""
    message = MagicMock(spec=Message)
    message.from_user = MagicMock(spec=User)
    message.from_user.id = 123456789
    message.from_user.first_name = "Test"
    message.from_user.last_name = "User"
    message.from_user.username = "testuser"
    message.answer = AsyncMock()
    return message


@pytest.fixture
def mock_state():
    """Create mock FSM state."""
    state = MagicMock(spec=FSMContext)
    state.clear = AsyncMock()
    state.set_state = AsyncMock()
    state.update_data = AsyncMock()
    state.get_data = AsyncMock(return_value={})
    return state


@pytest.fixture
def mock_command():
    """Create mock command object."""
    command = MagicMock()
    command.args = None
    return command


class TestCmdStart:
    """Test /start command handler."""

    @patch("sputnik_offer_crm.bot.handlers.registration.get_session")
    @patch("sputnik_offer_crm.bot.handlers.registration.show_student_menu")
    async def test_start_existing_student(
        self, mock_show_menu, mock_get_session, mock_message, mock_state, mock_command, db_session, student
    ):
        """Test /start for existing student shows student menu."""
        mock_get_session.return_value.__aenter__.return_value = db_session
        mock_show_menu.return_value = None
        mock_message.from_user.id = student.telegram_id

        await cmd_start(mock_message, mock_state, mock_command)

        mock_show_menu.assert_called_once_with(mock_message)
        mock_state.clear.assert_called_once()

    @patch("sputnik_offer_crm.bot.handlers.registration.get_session")
    async def test_start_existing_mentor(
        self, mock_get_session, mock_message, mock_state, mock_command, db_session, mentor
    ):
        """Test /start for existing mentor shows mentor menu."""
        mock_get_session.return_value.__aenter__.return_value = db_session
        mock_message.from_user.id = mentor.telegram_id

        with patch("sputnik_offer_crm.bot.handlers.mentor.show_mentor_menu") as mock_show_menu:
            mock_show_menu.return_value = None
            await cmd_start(mock_message, mock_state, mock_command)

            mock_show_menu.assert_called_once_with(mock_message)
            mock_state.clear.assert_called_once()

    @patch("sputnik_offer_crm.bot.handlers.registration.get_session")
    @patch("sputnik_offer_crm.bot.handlers.registration.process_invite_code")
    async def test_start_guest_with_code(
        self, mock_process, mock_get_session, mock_message, mock_state, mock_command, db_session
    ):
        """Test /start for guest with invite code."""
        mock_get_session.return_value.__aenter__.return_value = db_session
        mock_process.return_value = None
        mock_command.args = "TEST1234"

        await cmd_start(mock_message, mock_state, mock_command)

        mock_process.assert_called_once_with(mock_message, mock_state, "TEST1234")

    @patch("sputnik_offer_crm.bot.handlers.registration.get_session")
    async def test_start_guest_without_code(
        self, mock_get_session, mock_message, mock_state, mock_command, db_session
    ):
        """Test /start for guest without invite code."""
        mock_get_session.return_value.__aenter__.return_value = db_session
        mock_command.args = None

        await cmd_start(mock_message, mock_state, mock_command)

        mock_message.answer.assert_called_once()
        assert "код приглашения" in mock_message.answer.call_args[0][0].lower()
        mock_state.set_state.assert_called_once_with(RegistrationStates.waiting_for_code)


class TestProcessInviteCode:
    """Test invite code processing."""

    @patch("sputnik_offer_crm.bot.handlers.registration.get_session")
    async def test_process_invite_code_not_found(
        self, mock_get_session, mock_message, mock_state, db_session
    ):
        """Test processing non-existent invite code."""
        mock_get_session.return_value.__aenter__.return_value = db_session

        await process_invite_code(mock_message, mock_state, "NOTEXIST")

        mock_message.answer.assert_called_once()
        assert "не найден" in mock_message.answer.call_args[0][0].lower()

    @patch("sputnik_offer_crm.bot.handlers.registration.get_session")
    async def test_process_invite_code_already_used(
        self, mock_get_session, mock_message, mock_state, db_session, used_invite_code
    ):
        """Test processing already used invite code."""
        mock_get_session.return_value.__aenter__.return_value = db_session

        await process_invite_code(mock_message, mock_state, used_invite_code.code)

        mock_message.answer.assert_called_once()
        assert "уже был использован" in mock_message.answer.call_args[0][0].lower()

    @patch("sputnik_offer_crm.bot.handlers.registration.get_session")
    @patch("sputnik_offer_crm.bot.handlers.registration.get_timezone_keyboard")
    async def test_process_invite_code_success(
        self, mock_keyboard, mock_get_session, mock_message, mock_state, db_session, invite_code
    ):
        """Test successful invite code processing."""
        mock_get_session.return_value.__aenter__.return_value = db_session
        mock_keyboard.return_value = MagicMock()

        await process_invite_code(mock_message, mock_state, invite_code.code)

        mock_state.update_data.assert_called_once_with(invite_code_str=invite_code.code)
        mock_message.answer.assert_called_once()
        assert "код принят" in mock_message.answer.call_args[0][0].lower()
        mock_state.set_state.assert_called_once_with(RegistrationStates.waiting_for_timezone)


class TestHandleInviteCodeInput:
    """Test invite code input handler."""

    @patch("sputnik_offer_crm.bot.handlers.registration.process_invite_code")
    async def test_handle_invite_code_input(
        self, mock_process, mock_message, mock_state
    ):
        """Test handling invite code input."""
        mock_message.text = "  TEST1234  "
        mock_process.return_value = None

        await handle_invite_code_input(mock_message, mock_state)

        mock_process.assert_called_once_with(mock_message, mock_state, "TEST1234")

    @patch("sputnik_offer_crm.bot.handlers.registration.process_invite_code")
    async def test_handle_invite_code_input_strips_whitespace(
        self, mock_process, mock_message, mock_state
    ):
        """Test that invite code input strips whitespace."""
        mock_message.text = "\n\tCODE123\t\n"
        mock_process.return_value = None

        await handle_invite_code_input(mock_message, mock_state)

        mock_process.assert_called_once_with(mock_message, mock_state, "CODE123")
