"""ChatBot Hub analytics snapshot job."""

from __future__ import annotations

import logging
import os
from datetime import date

from sqlmodel import Session

from app.core.db import engine
from app.domain.chatbot.analytics_snapshots import (
    refresh_all_chatbot_analytics_snapshots,
)

log = logging.getLogger("chatbot_analytics_snapshot_job")


def _target_date_from_env() -> date | None:
    raw = os.getenv("CHATBOT_ANALYTICS_SNAPSHOT_DATE")
    if not raw:
        return None
    try:
        return date.fromisoformat(raw)
    except ValueError:
        log.warning("Ignoring invalid CHATBOT_ANALYTICS_SNAPSHOT_DATE=%s", raw)
        return None


def run_chatbot_analytics_snapshot_job(
    *,
    target_date: date | None = None,
    session: Session | None = None,
) -> dict[str, int]:
    """Refresh chatbot analytics snapshots and return counts by workspace."""
    if session is not None:
        result = refresh_all_chatbot_analytics_snapshots(session, target_date=target_date)
        session.commit()
        return result

    with Session(engine) as owned_session:
        result = refresh_all_chatbot_analytics_snapshots(owned_session, target_date=target_date)
        owned_session.commit()
        return result


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    result = run_chatbot_analytics_snapshot_job(target_date=_target_date_from_env())
    log.info("Chatbot analytics snapshots refreshed for %d workspace(s)", len(result))


if __name__ == "__main__":
    main()
