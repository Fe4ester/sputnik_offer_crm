"""Main router for bot handlers."""

from aiogram import Router

from sputnik_offer_crm.bot.handlers.registration import router as registration_router

router = Router()
router.include_router(registration_router)
