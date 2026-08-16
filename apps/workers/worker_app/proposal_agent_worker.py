"""Bounded scheduled runner for durable Proposal Agent jobs."""

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
from app.domain.proposal_agent.ecrm_adapter import EcrmProposalAdapter  # noqa: E402
from app.domain.proposal_agent.service import (  # noqa: E402
    recover_expired_proposal_leases,
    run_proposal_batch,
)

logger = logging.getLogger(__name__)

PROPOSAL_AGENT_BATCH_SIZE = 25


def process_proposal_agent_batch(adapter: EcrmProposalAdapter) -> int:
    """Recover safe leases, then process one bounded batch through the eCRM seam."""

    with Session(engine) as session:
        recovered = recover_expired_proposal_leases(session)
        if recovered:
            session.commit()
            logger.warning("Recovered %d proposal agent lease(s)", recovered)
        return run_proposal_batch(
            session,
            adapter=adapter,
            limit=PROPOSAL_AGENT_BATCH_SIZE,
        )
