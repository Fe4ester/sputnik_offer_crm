"""Bot keyboards."""

from sputnik_offer_crm.bot.keyboards.mentor import (
    get_direction_selection_keyboard,
    get_mentor_menu_keyboard,
)
from sputnik_offer_crm.bot.keyboards.registration import (
    get_other_timezone_keyboard,
    get_timezone_confirmation_keyboard,
    get_timezone_keyboard,
)
from sputnik_offer_crm.bot.keyboards.student import get_student_menu_keyboard

__all__ = [
    "get_timezone_keyboard",
    "get_other_timezone_keyboard",
    "get_timezone_confirmation_keyboard",
    "get_mentor_menu_keyboard",
    "get_direction_selection_keyboard",
    "get_student_menu_keyboard",
]
