"""Module: ``main``."""

from fastapi import APIRouter

from app.api.routes import (
    accounts,
    audit_log,
    calls,
    campaign_health,
    campaigns,
    contacts,
    controls,
    customer_360,
    dashboard,
    engagement_intelligence,
    ecrm_installations,
    kpis,
    login,
    oidc,
    onboarding,
    platform_admin,
    platform_shared,
    private,
    prospecting,
    provider_credentials,
    public_branding,
    revenue_interventions,
    revenue_essentials,
    scheduling,
    scripts,
    sequences,
    signals,
    suite_context,
    templates,
    tenant_admin,
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
api_router.include_router(ecrm_installations.router)
api_router.include_router(calls.router)
api_router.include_router(customer_360.router)
api_router.include_router(accounts.router)
api_router.include_router(contacts.router)
api_router.include_router(platform_shared.router)
api_router.include_router(prospecting.router)
api_router.include_router(provider_credentials.router)
api_router.include_router(scheduling.router)
api_router.include_router(workspace_runtime_config.router)
api_router.include_router(audit_log.router)
api_router.include_router(kpis.router)
api_router.include_router(chatbot_router)
api_router.include_router(public_branding.router)
api_router.include_router(platform_admin.router)
api_router.include_router(tenant_admin.router)
api_router.include_router(suite_context.router)
api_router.include_router(onboarding.router)
api_router.include_router(revenue_interventions.router)
api_router.include_router(revenue_essentials.router)
api_router.include_router(oidc.router)


if settings.ENVIRONMENT == "local":
    api_router.include_router(private.router)
