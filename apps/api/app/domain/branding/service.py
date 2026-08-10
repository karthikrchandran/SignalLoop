from __future__ import annotations

import hashlib
import io
import re
from uuid import UUID

from PIL import Image, UnidentifiedImageError

from app.domain.branding.models import (
    BrandingLifecycle,
    TenantBrandAsset,
    TenantBrandingVersion,
)
from app.domain.branding.storage import BrandAssetStore, InMemoryBrandAssetStore


class BrandAssetValidationError(ValueError):
    """The supplied branding asset is unsafe or invalid."""


class BrandingService:
    MAX_BYTES = 5 * 1024 * 1024
    ALLOWED_MIME = {"image/png", "image/jpeg", "image/webp"}
    _HEX_COLOR = re.compile(r"^#[0-9a-fA-F]{6}$")

    def __init__(self, store: BrandAssetStore | None = None) -> None:
        self.store = store or InMemoryBrandAssetStore()
        self._versions: dict[UUID, TenantBrandingVersion] = {}
        self._next_version: dict[UUID, int] = {}

    def store_asset(
        self,
        tenant_id: UUID,
        mime_type: str,
        content: bytes,
        *,
        kind: str = "LOGO",
        created_by: UUID | None = None,
    ) -> TenantBrandAsset:
        if mime_type not in self.ALLOWED_MIME:
            raise BrandAssetValidationError(
                "only PNG, JPEG, and WebP assets are supported"
            )
        if len(content) == 0 or len(content) > self.MAX_BYTES:
            raise BrandAssetValidationError("asset must be between 1 byte and 5 MB")
        try:
            with Image.open(io.BytesIO(content)) as image:
                image.verify()
            with Image.open(io.BytesIO(content)) as image:
                if (
                    image.format not in {"PNG", "JPEG", "WEBP"}
                    or image.width > 4096
                    or image.height > 4096
                    or image.width * image.height > 20_000_000
                ):
                    raise BrandAssetValidationError(
                        "asset dimensions or format are not allowed"
                    )
                output = io.BytesIO()
                image.save(output, format=image.format, optimize=True)
                normalized = output.getvalue()
        except (UnidentifiedImageError, OSError) as exc:
            raise BrandAssetValidationError("asset is not a valid image") from exc
        if len(normalized) > self.MAX_BYTES:
            raise BrandAssetValidationError("normalized asset exceeds 5 MB")
        asset = TenantBrandAsset(
            tenant_id=tenant_id,
            kind=kind,
            mime_type=mime_type,
            content=normalized,
            byte_count=len(normalized),
            sha256=hashlib.sha256(normalized).hexdigest(),
            created_by=created_by,
        )
        return self.store.put(asset)

    def create_draft(
        self,
        tenant_id: UUID,
        *,
        display_name: str,
        headline: str,
        supporting_copy: str,
        **kwargs: object,
    ) -> TenantBrandingVersion:
        self._validate_text(display_name, 3, 80)
        self._validate_text(headline, 3, 120)
        self._validate_text(supporting_copy, 3, 300)
        version = self._next_version.get(tenant_id, 0) + 1
        self._next_version[tenant_id] = version
        draft = TenantBrandingVersion(
            tenant_id=tenant_id,
            version=version,
            display_name=display_name,
            headline=headline,
            supporting_copy=supporting_copy,
            **kwargs,
        )
        self._versions[draft.id] = draft
        return draft

    def update_draft(
        self, version_id: UUID, **changes: object
    ) -> TenantBrandingVersion:
        version = self._versions[version_id]
        if version.lifecycle != BrandingLifecycle.DRAFT:
            raise ValueError("only drafts can be edited")
        for key, value in changes.items():
            if not hasattr(version, key):
                raise ValueError(f"unknown branding field: {key}")
            setattr(version, key, value)
        return version

    def publish(
        self, version_id: UUID, *, published_by: UUID | None = None
    ) -> TenantBrandingVersion:
        version = self._versions[version_id]
        if version.lifecycle not in {
            BrandingLifecycle.DRAFT,
            BrandingLifecycle.VALIDATED,
        }:
            raise ValueError("only a draft or validated version can publish")
        version.lifecycle = BrandingLifecycle.PUBLISHED
        version.published_by = published_by
        from datetime import datetime, timezone

        version.published_at = datetime.now(timezone.utc)
        return version

    @staticmethod
    def _validate_text(value: str, minimum: int, maximum: int) -> None:
        if not minimum <= len(value.strip()) <= maximum:
            raise ValueError(f"text must be {minimum}-{maximum} characters")
