from __future__ import annotations

from datetime import timedelta

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from sqlmodel import Session, SQLModel, create_engine, select

from app.domain.projections.dispatcher import (
    DeliveryResponse,
    ProjectionDispatcher,
    recover_expired_projection_leases,
)
from app.domain.projections.outbox import enqueue_projection
from app.domain.tenants.models import (
    ProductCode,
    ProductInstallation,
    SuiteProjectionAttempt,
    SuiteProjectionOutbox,
    Tenant,
    utc_now,
)


class RecordingTransport:
    def __init__(self, response: DeliveryResponse) -> None:
        self.response = response
        self.requests: list[tuple[str, bytes, dict[str, str]]] = []

    def post(self, url: str, body: bytes, headers: dict[str, str]) -> DeliveryResponse:
        self.requests.append((url, body, headers))
        return self.response


def _session() -> Session:
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
    return Session(engine)


def _projection(session: Session) -> SuiteProjectionOutbox:
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
    return enqueue_projection(
        session,
        tenant_id=tenant.id,
        installation_id=installation.id,
        projection_kind="tenant_membership",
        projection_version=1,
        payload={"roles": ["EMPLOYEE"], "user_id": "user-123"},
    )


def _dispatcher(response: DeliveryResponse) -> tuple[ProjectionDispatcher, RecordingTransport]:
    transport = RecordingTransport(response)
    return (
        ProjectionDispatcher(
            private_key=Ed25519PrivateKey.generate(),
            transport=transport,
        ),
        transport,
    )


def test_dispatcher_acknowledges_signed_projection_receipt() -> None:
    with _session() as session:
        projection = _projection(session)
        dispatcher, transport = _dispatcher(
            DeliveryResponse(status_code=202, body={"event_id": str(projection.event_id), "accepted": True})
        )

        dispatcher.dispatch(session, projection.id)

        session.refresh(projection)
        assert projection.status == "ACKNOWLEDGED"
        assert projection.acknowledgement_receipt == {
            "event_id": str(projection.event_id),
            "accepted": True,
        }
        attempt = session.exec(select(SuiteProjectionAttempt)).one()
        assert attempt.outcome == "ACKNOWLEDGED"
        assert attempt.http_status == 202
        assert transport.requests[0][0].endswith("/api/platform/projections")
        assert transport.requests[0][2]["Authorization"].startswith("Bearer ")


def test_dispatcher_schedules_transient_failure_for_retry() -> None:
    with _session() as session:
        projection = _projection(session)
        dispatcher, _ = _dispatcher(DeliveryResponse(status_code=503, body={"error": "unavailable"}))

        dispatcher.dispatch(session, projection.id)

        session.refresh(projection)
        assert projection.status == "RETRY_SCHEDULED"
        assert projection.attempt_count == 1
        assert projection.next_attempt_at is not None
        assert projection.dead_letter_reason is None
        attempt = session.exec(select(SuiteProjectionAttempt)).one()
        assert attempt.outcome == "RETRY_SCHEDULED"
        assert attempt.http_status == 503


def test_dispatcher_dead_letters_permanent_delivery_rejection() -> None:
    with _session() as session:
        projection = _projection(session)
        dispatcher, _ = _dispatcher(DeliveryResponse(status_code=422, body={"error": "invalid"}))

        dispatcher.dispatch(session, projection.id)

        session.refresh(projection)
        assert projection.status == "DEAD_LETTER"
        assert projection.attempt_count == 1
        assert projection.dead_letter_reason == "HTTP_422"


def test_expired_in_flight_lease_returns_projection_to_pending() -> None:
    with _session() as session:
        projection = _projection(session)
        projection.status = "IN_FLIGHT"
        projection.lease_expires_at = utc_now() - timedelta(seconds=1)
        session.add(projection)
        session.commit()

        recovered = recover_expired_projection_leases(session)

        session.refresh(projection)
        assert recovered == 1
        assert projection.status == "PENDING"
        assert projection.lease_expires_at is None
