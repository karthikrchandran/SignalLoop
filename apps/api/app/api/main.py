"""Module: ``main``."""

from fastapi import APIRouter

from app.api.routes import (
    audit_log,
    calls,
    campaign_health,
    campaigns,
    contacts,
    controls,
    dashboard,
    kpis,
    login,
    private,
    provider_credentials,
    scripts,
    sequences,
    signals,
    templates,
    triggers,
    users,
    utils,
    voice,
    webhooks,
)
from app.core.config import settings

api_router = APIRouter()
api_router.include_router(login.router)
api_router.include_router(users.router)
api_router.include_router(utils.router)
api_router.include_router(campaigns.router)
api_router.include_router(campaign_health.router)
api_router.include_router(templates.router)
api_router.include_router(controls.router)
api_router.include_router(scripts.router)
api_router.include_router(sequences.router)
api_router.include_router(voice.router)
api_router.include_router(webhooks.router)
api_router.include_router(signals.router)
api_router.include_router(triggers.router)
api_router.include_router(dashboard.router)
api_router.include_router(calls.router)
api_router.include_router(contacts.router)
api_router.include_router(provider_credentials.router)
api_router.include_router(audit_log.router)
api_router.include_router(kpis.router)


if settings.ENVIRONMENT == "local":
    api_router.include_router(private.router)
