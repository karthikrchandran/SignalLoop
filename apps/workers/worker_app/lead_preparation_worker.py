"""Scheduled adapter for the durable Lead Preparation Agent worker."""

from __future__ import annotations

import logging
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[4]
_API_SRC = _REPO_ROOT / "apps" / "api"
if str(_API_SRC) not in sys.path:
    sys.path.insert(0, str(_API_SRC))

from sqlmodel import Session  # noqa: E402

from app.core.db import engine  # noqa: E402
from app.domain.lead_preparation.service import (  # noqa: E402
    recover_expired_preparation_leases,
)
from app.domain.lead_preparation.worker import run_lead_preparation_batch  # noqa: E402
from app.domain_models import Contact  # noqa: E402

logger = logging.getLogger(__name__)

LEAD_PREPARATION_POLL_INTERVAL_SECONDS = 30
LEAD_PREPARATION_BATCH_SIZE = 25


def _collect_internal_contact_evidence(contact: Contact) -> dict[str, str]:
    """Use persisted first-party fields only; do not invent external evidence."""

    visible_facts = [
        value
        for value in (
            contact.company,
            contact.source_channel,
            ", ".join(contact.intent_json),
        )
        if value
    ]
    return {
        "source_type": "signal_loop_contact",
        "source_reference": f"contact:{contact.id}",
        "redacted_excerpt": " | ".join(visible_facts)[:2000],
    }


def process_lead_preparation_batch() -> int:
    """Recover leases and process one bounded database-backed batch."""

    with Session(engine) as session:
        recovered = recover_expired_preparation_leases(session)
        if recovered:
            session.commit()
            logger.warning(
                "Recovered %d expired lead preparation lease(s)", recovered
            )
        return run_lead_preparation_batch(
            session,
            evidence_collector=_collect_internal_contact_evidence,
            limit=LEAD_PREPARATION_BATCH_SIZE,
        )
