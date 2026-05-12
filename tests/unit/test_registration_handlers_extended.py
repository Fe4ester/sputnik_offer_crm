"""Additional tests for registration handlers."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message, User

from sputnik_offer_crm.bot.handlers.registration import (
    complete_registration,
    handle_timezone_confirmation,
    handle_timezone_selection,
)
from sputnik_offer_crm.bot.states import RegistrationStates

pytest_plugins = ["tests.fixtures.db_fixtures"]


@pytest.fixture
def mock_callback():
    """Create mock callback query."""
    callback = MagicMock(spec=CallbackQuery)
    callback.from_user = MagicMock(spec=User)
    callback.from_user.id = 123456789
    callback.from_user.first_name = "Test"
    callback.from_user.last_name = "User"
    callback.from_user.username = "testuser"
    callback.answer = AsyncMock()
    callback.message = MagicMock(spec=Message)
    callback.message.edit_text = AsyncMock()
    callback.data = ""
    return callback


@pytest.fixture
def mock_state():
    """Create mock FSM state."""
    state = MagicMock(spec=FSMContext)
    state.clear = AsyncMock()
    state.set_state = AsyncMock()
    state.update_data = AsyncMock()
    state.get_data = AsyncMock(return_value={"invite_code_str": "TEST1234"})
    return state


class TestTimezoneHandlers:
    """Test timezone selection handlers."""

    @patch("sputnik_offer_crm.bot.handlers.registration.get_other_timezone_keyboard")
    async def test_handle_timezone_selection_other(self, mock_keyboard, mock_callback, mock_state):
        """Test timezone selection with 'other' option."""
        mock_callback.data = "tz:other"
        mock_keyboard.return_value = MagicMock()

        await handle_timezone_selection(mock_callback, mock_state)

        mock_callback.answer.assert_called_once()
        mock_callback.message.edit_text.assert_called_once()
        assert "Выберите часовой пояс" in mock_callback.message.edit_text.call_args[0][0]

    @patch("sputnik_offer_crm.bot.handlers.registration.get_timezone_keyboard")
    async def test_handle_timezone_selection_back(self, mock_keyboard, mock_callback, mock_state):
        """Test timezone selection with 'back' option."""
        mock_callback.data = "tz:back"
        mock_keyboard.return_value = MagicMock()

        await handle_timezone_selection(mock_callback, mock_state)

        mock_callback.answer.assert_called_once()
        mock_callback.message.edit_text.assert_called_once()

    async def test_handle_timezone_selection_input_time(self, mock_callback, mock_state):
        """Test timezone selection with 'input_time' option."""
        mock_callback.data = "tz:input_time"

        await handle_timezone_selection(mock_callback, mock_state)

        mock_callback.answer.assert_called_once()
        mock_callback.message.edit_text.assert_called_once()
        assert "Введите ваше текущее локальное время" in mock_callback.message.edit_text.call_args[0][0]
        mock_state.set_state.assert_called_once_with(RegistrationStates.waiting_for_local_time)

    @patch("sputnik_offer_crm.bot.handlers.registration.complete_registration")
    async def test_handle_timezone_selection_direct(self, mock_complete, mock_callback, mock_state):
        """Test direct timezone selection."""
        mock_callback.data = "tz:Europe/Moscow"
        mock_complete.return_value = None

        await handle_timezone_selection(mock_callback, mock_state)

        mock_callback.answer.assert_called_once()
        mock_complete.assert_called_once_with(mock_callback, mock_state, "Europe/Moscow")


class TestCompleteRegistration:
    """Test complete registration handler."""

    @patch("sputnik_offer_crm.bot.handlers.registration.get_session")
    async def test_complete_registration_missing_invite_code(
        self, mock_get_session, mock_callback, db_session
    ):
        """Test complete registration with missing invite code in state."""
        mock_get_session.return_value.__aenter__.return_value = db_session
        mock_state = MagicMock(spec=FSMContext)
        mock_state.get_data = AsyncMock(return_value={})
        mock_state.clear = AsyncMock()

        await complete_registration(mock_callback, mock_state, "Europe/Moscow")

        mock_callback.message.edit_text.assert_called_once()
        assert "Ошибка" in mock_callback.message.edit_text.call_args[0][0]
        mock_state.clear.assert_called_once()

    @patch("sputnik_offer_crm.bot.handlers.registration.get_session")
    async def test_complete_registration_success(
        self, mock_get_session, mock_callback, mock_state, db_session, invite_code, stage
    ):
        """Test successful registration completion."""
        mock_get_session.return_value.__aenter__.return_value = db_session

        await complete_registration(mock_callback, mock_state, "Europe/Moscow")

        mock_callback.message.edit_text.assert_called_once()
        assert "Регистрация завершена" in mock_callback.message.edit_text.call_args[0][0]
        mock_state.clear.assert_called_once()
