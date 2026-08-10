from __future__ import annotations

from typing import Protocol
from uuid import UUID

from app.domain.branding.models import TenantBrandAsset


class BrandAssetStore(Protocol):
    def put(self, asset: TenantBrandAsset) -> TenantBrandAsset: ...
    def get(self, asset_id: UUID) -> TenantBrandAsset | None: ...


class InMemoryBrandAssetStore:
    def __init__(self) -> None:
        self._assets: dict[UUID, TenantBrandAsset] = {}

    def put(self, asset: TenantBrandAsset) -> TenantBrandAsset:
        self._assets[asset.id] = asset
        return asset

    def get(self, asset_id: UUID) -> TenantBrandAsset | None:
        return self._assets.get(asset_id)
