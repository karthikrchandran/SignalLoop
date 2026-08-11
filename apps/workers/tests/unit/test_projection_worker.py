from __future__ import annotations

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from sqlmodel import Session, SQLModel, create_engine

from app.domain.projections.dispatcher import DeliveryResponse, ProjectionDispatcher
from app.domain.projections.outbox import enqueue_projection
from app.domain.tenants.models import (
    ProductCode,
    ProductInstallation,
    SuiteProjectionAttempt,
    SuiteProjectionOutbox,
    Tenant,
)
from worker_app.projection_worker import process_claimed_projections


class AcceptingTransport:
    def post(self, _url: str, _body: bytes, headers: dict[str, str]) -> DeliveryResponse:
        return DeliveryResponse(
            status_code=202,
            body={"event_id": headers["X-Projection-Event-Id"], "accepted": True},
        )


def test_worker_claims_and_acknowledges_due_projection() -> None:
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False})
    SQLModel.metadata.create_all(
        engine,
        tables=[
            Tenant.__table__,
            ProductInstallation.__table__,
            SuiteProjectionOutbox.__table__,
            SuiteProjectionAttempt.__table__,
        ],
    )
    with Session(engine) as session:
        tenant = Tenant(key="ara-global", display_name="ARA Global")
        session.add(tenant)
        session.flush()
        installation = ProductInstallation(
            tenant_id=tenant.id,
            product_code=ProductCode.REVENUE_OS,
            local_identifier="org-ara",
            projection_endpoint="https://revenueos.example.test/api/platform/projections",
            workload_key_id="signalloop-2026-08",
        )
        session.add(installation)
        session.flush()
        projection = enqueue_projection(
            session,
            tenant_id=tenant.id,
            installation_id=installation.id,
            projection_kind="tenant_membership",
            projection_version=1,
            payload={"user_id": "user-123"},
        )
        session.commit()
        dispatcher = ProjectionDispatcher(
            private_key=Ed25519PrivateKey.generate(),
            transport=AcceptingTransport(),
        )

        processed = process_claimed_projections(session, dispatcher)

        session.refresh(projection)
        assert processed == 1
        assert projection.status == "ACKNOWLEDGED"
