"""Keyboards for student flow."""

from aiogram.types import KeyboardButton, ReplyKeyboardMarkup


def get_student_menu_keyboard() -> ReplyKeyboardMarkup:
    """Get main menu keyboard for student."""
    keyboard = [
        [KeyboardButton(text="📊 Мой прогресс")],
        [KeyboardButton(text="📅 Мои дедлайны")],
    ]
    return ReplyKeyboardMarkup(
        keyboard=keyboard,
        resize_keyboard=True,
    )
