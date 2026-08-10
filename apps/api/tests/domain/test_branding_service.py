from __future__ import annotations

import io
import uuid

import pytest
from PIL import Image

from app.domain.branding.service import BrandAssetValidationError, BrandingService


def _png(width: int = 32, height: int = 32) -> bytes:
    image = Image.new("RGB", (width, height), "white")
    output = io.BytesIO()
    image.save(output, format="PNG")
    return output.getvalue()


def test_rejects_active_content_assets() -> None:
    service = BrandingService()
    for mime in ("image/svg+xml", "text/html", "application/javascript"):
        with pytest.raises(BrandAssetValidationError):
            service.store_asset(uuid.uuid4(), mime, b"payload")


def test_rejects_asset_over_five_megabytes() -> None:
    with pytest.raises(BrandAssetValidationError):
        BrandingService().store_asset(
            uuid.uuid4(), "image/png", b"x" * (5 * 1024 * 1024 + 1)
        )


def test_rejects_fake_png_and_excessive_dimensions() -> None:
    service = BrandingService()
    with pytest.raises(BrandAssetValidationError):
        service.store_asset(uuid.uuid4(), "image/png", b"not-a-png")
    with pytest.raises(BrandAssetValidationError):
        service.store_asset(uuid.uuid4(), "image/png", _png(4097, 10))


def test_normalizes_asset_and_creates_immutable_versions() -> None:
    service = BrandingService()
    tenant_id = uuid.uuid4()
    asset = service.store_asset(tenant_id, "image/png", _png())
    draft = service.create_draft(
        tenant_id,
        display_name="ARA Global",
        headline="Revenue workspace",
        supporting_copy="Coordinate every customer commitment.",
    )
    published = service.publish(draft.id)

    assert asset.tenant_id == tenant_id
    assert asset.mime_type == "image/png"
    assert asset.sha256
    assert published.lifecycle == "PUBLISHED"
    with pytest.raises(ValueError):
        service.update_draft(published.id, headline="cannot mutate")
