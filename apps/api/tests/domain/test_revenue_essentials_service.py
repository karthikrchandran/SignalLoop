from datetime import UTC, datetime
from uuid import uuid4

from app.domain.revenue_essentials.service import build
from app.domain.tenants.capabilities import SuiteContext
from app.domain.tenants.models import RoleBundle


def test_essentials_returns_an_explicit_empty_state_when_no_signed_source_exists() -> None:
    result = build(
        SuiteContext(uuid4(), uuid4(), frozenset({"commitarc"}), frozenset({RoleBundle.EMPLOYEE}), frozenset({"revenueos.essentials.read"})),
        now=datetime(2026, 8, 10, tzinfo=UTC),
    )
    assert result.cards == []
    assert result.source_freshness[0].status == "UNAVAILABLE"
    assert result.blocked_actions
