from __future__ import annotations

import uuid
from datetime import datetime

from sqlmodel import SQLModel


class SequenceCreate(SQLModel):
    name: str
    campaign_id: uuid.UUID


class SequenceUpdate(SQLModel):
    name: str | None = None
    active: bool | None = None


class StepPayload(SQLModel):
    step_order: int
    delay_days: int = 0
    subject_template: str
    body_template: str


class StepsBatchUpdate(SQLModel):
    steps: list[StepPayload]


class StepPublic(SQLModel):
    id: uuid.UUID
    step_order: int
    delay_days: int
    subject_template: str
    body_template: str


class SequencePublic(SQLModel):
    id: uuid.UUID
    campaign_id: uuid.UUID
    name: str
    active: bool
    created_at: datetime


class SequenceDetailPublic(SequencePublic):
    steps: list[StepPublic] = []


class SequencesPublic(SQLModel):
    data: list[SequencePublic]
    count: int


class EnrollmentResult(SQLModel):
    enrolled: int
    message: str
