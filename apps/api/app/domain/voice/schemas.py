from __future__ import annotations

import uuid
from datetime import datetime

from sqlmodel import SQLModel


class ScriptCreate(SQLModel):
    name: str
    campaign_id: uuid.UUID
    content: str


class ScriptUpdate(SQLModel):
    name: str | None = None
    content: str | None = None
    active: bool | None = None


class QAPairPublic(SQLModel):
    question: str
    answer: str


class ScriptParsedPublic(SQLModel):
    opening_pitch: str
    qa_pairs: list[QAPairPublic]
    fallback_response: str
    scheduling_question: str


class ScriptPublic(SQLModel):
    id: uuid.UUID
    campaign_id: uuid.UUID
    name: str
    active: bool
    created_at: datetime


class ScriptDetailPublic(ScriptPublic):
    content: str
    parsed: ScriptParsedPublic | None = None


class ScriptsPublic(SQLModel):
    data: list[ScriptPublic]
    count: int
