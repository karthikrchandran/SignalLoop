"""Scheduled adapter for automated lead discovery, entity resolution, and AI scoring."""

from __future__ import annotations

import logging
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[3]
_API_SRC = _REPO_ROOT / "apps" / "api"
if str(_API_SRC) not in sys.path:
    sys.path.insert(0, str(_API_SRC))

from sqlmodel import Session, select  # noqa: E402

from app.core.db import engine  # noqa: E402
from app.domain.lead_discovery.models import (  # noqa: E402
    DiscoveredLeadRecord,
    LeadFitBand,
)
from app.domain.lead_discovery.resolution import resolve_lead_entity  # noqa: E402
from app.domain.lead_discovery.scoring import score_discovered_lead  # noqa: E402
from app.domain.lead_discovery.service import _lead_to_dto  # noqa: E402
from app.domain_models import Contact  # noqa: E402

logger = logging.getLogger(__name__)

LEAD_DISCOVERY_POLL_INTERVAL_SECONDS = 300
LEAD_DISCOVERY_BATCH_SIZE = 25


def process_lead_discovery_batch(session: Session, limit: int = LEAD_DISCOVERY_BATCH_SIZE) -> int:
    """Process unscored or stale discovered leads: resolve entities and evaluate AI score."""
    leads = session.exec(
        select(DiscoveredLeadRecord)
        .where(
            DiscoveredLeadRecord.fit_score == 0,
            DiscoveredLeadRecord.is_promoted == False,  # noqa: E712
        )
        .limit(limit)
    ).all()

    if not leads:
        return 0

    processed_count = 0
    for lead in leads:
        workspace_id = lead.workspace_id
        # Collect existing contacts for this workspace
        contacts = session.exec(
            select(Contact).where(Contact.workspace_id == workspace_id)
        ).all()

        accounts_data = [
            {"id": str(getattr(c, "shared_account_id", "") or ""), "name": c.company or "", "domain": c.email.split("@", 1)[1]}
            for c in contacts
            if "@" in c.email and c.company
        ]
        contacts_data = [{"email": c.email, "account_id": getattr(c, "shared_account_id", None)} for c in contacts]

        # Entity resolution
        conf, match = resolve_lead_entity(
            domain=lead.company_domain,
            company_name=lead.company_name,
            existing_accounts=accounts_data,
            existing_contacts=contacts_data,
        )
        lead.match_confidence = conf
        if match:
            lead.matched_account_id = str(match.get("id") or "")

        # AI Scoring
        dto = _lead_to_dto(lead)
        score_res = score_discovered_lead(dto)
        lead.fit_score = score_res.fit_score
        lead.fit_band = score_res.fit_band
        lead.score_rationale = score_res.rationale
        lead.conversation_starters_json = score_res.conversation_starters

        session.add(lead)
        processed_count += 1

    session.commit()
    logger.info("Processed and scored %d discovered lead(s)", processed_count)
    return processed_count


def run_lead_discovery_scheduled_batch() -> int:
    """Entry point for AsyncIOScheduler."""
    with Session(engine) as session:
        return process_lead_discovery_batch(session)
