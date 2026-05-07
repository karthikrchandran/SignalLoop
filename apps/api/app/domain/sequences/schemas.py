"""Request/response schemas for the ``sequences`` domain."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlmodel import SQLModel


class SequenceCreate(SQLModel):
    """Request payload for creating sequence."""
    name: str
    campaign_id: uuid.UUID


class SequenceUpdate(SQLModel):
    """Request payload for updating sequence."""
    name: str | None = None
    active: bool | None = None


class StepPayload(SQLModel):
    """Step payload."""
    step_order: int
    delay_days: int = 0
    subject_template: str
    body_template: str


class StepsBatchUpdate(SQLModel):
    """Request payload for updating steps batch."""
    steps: list[StepPayload]


class StepPublic(SQLModel):
    """API response model: step."""
    id: uuid.UUID
    step_order: int
    delay_days: int
    subject_template: str
    body_template: str


class SequencePublic(SQLModel):
    """API response model: sequence."""
    id: uuid.UUID
    campaign_id: uuid.UUID
    name: str
    active: bool
    created_at: datetime


class SequenceDetailPublic(SequencePublic):
    """API response model: sequence detail."""
    steps: list[StepPublic] = []


class SequencesPublic(SQLModel):
    """API response model: sequences."""
    data: list[SequencePublic]
    count: int


class EnrollmentResult(SQLModel):
    """Result row: enrollment."""
    enrolled: int
    message: str
