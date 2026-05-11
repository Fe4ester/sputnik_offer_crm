"""FSM states for bot flows."""

from aiogram.fsm.state import State, StatesGroup


class RegistrationStates(StatesGroup):
    """States for student registration flow."""

    waiting_for_code = State()
    waiting_for_timezone = State()
    waiting_for_local_time = State()
    confirming_timezone = State()
