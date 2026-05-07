"""FastAPI router: ``offer_packs`` endpoints."""

# Offer-pack CRUD routes removed in Story 1.4 cleanup.
# The underlying DB tables (offer_packs, offer_pack_versions,
# offer_pack_template_bindings) are retained because
# CampaignChannelStrategy holds FK references to them.
# This file is intentionally empty; the router is no longer
# registered in app/api/main.py.

