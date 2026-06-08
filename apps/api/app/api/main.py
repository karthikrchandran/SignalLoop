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
    engagement_intelligence,
    kpis,
    login,
    private,
    prospecting,
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
    workspace_runtime_config,
)
from app.core.config import settings
from app.routers.chatbot import router as chatbot_router

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
api_router.include_router(engagement_intelligence.router)
api_router.include_router(calls.router)
api_router.include_router(contacts.router)
api_router.include_router(prospecting.router)
api_router.include_router(provider_credentials.router)
api_router.include_router(workspace_runtime_config.router)
api_router.include_router(audit_log.router)
api_router.include_router(kpis.router)
api_router.include_router(chatbot_router)


if settings.ENVIRONMENT == "local":
    api_router.include_router(private.router)
