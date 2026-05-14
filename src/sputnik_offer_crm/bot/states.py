"""FSM states for bot flows."""

from aiogram.fsm.state import State, StatesGroup


class RegistrationStates(StatesGroup):
    """States for student registration flow."""

    waiting_for_code = State()
    waiting_for_timezone = State()
    waiting_for_local_time = State()
    confirming_timezone = State()


class MentorInviteCodeStates(StatesGroup):
    """States for mentor invite code creation flow."""

    selecting_direction = State()
    selecting_timezone = State()


class MentorStudentViewStates(StatesGroup):
    """States for mentor student view flow."""

    waiting_for_search_query = State()
    confirming_next_stage = State()
    selecting_manual_stage = State()
    confirming_manual_stage = State()
    selecting_deadline_option = State()
    waiting_for_custom_deadline = State()
    confirming_deadline = State()
    confirming_bulk_deadlines = State()
    confirming_dropout = State()
    waiting_for_company = State()
    waiting_for_position = State()
    confirming_offer_completion = State()
    confirming_pause = State()
    confirming_resume = State()


class WeeklyReportStates(StatesGroup):
    """States for student weekly report submission flow."""

    waiting_for_what_did = State()
    waiting_for_problems_solved = State()
    waiting_for_problems_unsolved = State()


class DirectionManagementStates(StatesGroup):
    """States for direction and stage management flow."""

    entering_direction_code = State()
    entering_direction_name = State()
    entering_stage_title = State()
    entering_stage_description = State()
    entering_stage_duration = State()


class StudentTimezoneChangeStates(StatesGroup):
    """States for student timezone change flow."""

    selecting_timezone = State()
    selecting_other_timezone = State()
    waiting_for_local_time = State()
    confirming_timezone = State()
