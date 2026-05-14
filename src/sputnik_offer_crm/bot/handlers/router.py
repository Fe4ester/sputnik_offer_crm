"""Main router for bot handlers."""

from aiogram import Router

from sputnik_offer_crm.bot.handlers.direction_management import router as direction_management_router
from sputnik_offer_crm.bot.handlers.mentor import router as mentor_router
from sputnik_offer_crm.bot.handlers.mentor_analytics import router as mentor_analytics_router
from sputnik_offer_crm.bot.handlers.registration import router as registration_router
from sputnik_offer_crm.bot.handlers.student import router as student_router
from sputnik_offer_crm.bot.handlers.student_timezone import router as student_timezone_router

router = Router()
router.include_router(direction_management_router)
router.include_router(mentor_analytics_router)
router.include_router(student_timezone_router)
router.include_router(mentor_router)
router.include_router(student_router)
router.include_router(registration_router)
