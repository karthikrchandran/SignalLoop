from datetime import datetime

from pydantic import BaseModel


class SourceFreshness(BaseModel):
    source: str
    status: str
    message: str
    observed_at: datetime | None = None


class EssentialsCard(BaseModel):
    kind: str
    title: str
    detail: str
    owner_user_id: str


class RevenueEssentialsResponse(BaseModel):
    generated_at: datetime
    source_freshness: list[SourceFreshness]
    cards: list[EssentialsCard]
    metrics: list[dict[str, object]]
    blocked_actions: list[str]
    permitted_questions: list[str]
    personal_goals: list[dict[str, object]]
    intervention_outcomes: list[dict[str, object]]
