from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class ProductContext(BaseModel):
    visible: bool
    mode: str | None = None
    href: str | None = None
    capabilities: list[str] = Field(default_factory=list)


class SuiteContextResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    tenant: dict[str, str]
    roles: list[str]
    capabilities: list[str]
    products: dict[str, ProductContext]
    default_route: str
