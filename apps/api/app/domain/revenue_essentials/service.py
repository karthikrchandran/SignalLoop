from datetime import UTC, datetime

from app.domain.revenue_essentials.schemas import (
    RevenueEssentialsResponse,
    SourceFreshness,
)
from app.domain.tenants.capabilities import SuiteContext


def build(context: SuiteContext, *, now: datetime | None = None) -> RevenueEssentialsResponse:
    """Return only derived employee-safe content; never manufacture CRM values."""
    _ = context
    generated_at = now or datetime.now(UTC)
    return RevenueEssentialsResponse(
        generated_at=generated_at,
        source_freshness=[
            SourceFreshness(
                source="CommitArc",
                status="UNAVAILABLE",
                message="No signed CommitArc projection has been received for this tenant.",
            )
        ],
        cards=[],
        metrics=[],
        blocked_actions=["Connect a signed CommitArc projection before recommendations can be generated."],
        permitted_questions=[],
        personal_goals=[],
        intervention_outcomes=[],
    )
