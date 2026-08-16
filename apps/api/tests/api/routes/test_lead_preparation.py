from __future__ import annotations

import uuid
from datetime import datetime, timezone

from fastapi.testclient import TestClient
from sqlmodel import Session

from app.core.config import settings
from app.domain.commercial_agents.models import AgentDeployment, AgentDeploymentStatus
from app.domain.lead_preparation.models import LeadPreparationJobStatus
from app.domain.lead_preparation.scoring import build_default_scoring_policy
from app.domain.lead_preparation.service import enqueue_preparation_job
from app.domain.lead_preparation.worker import run_lead_preparation_batch
from app.domain_models import Contact
from tests.api.routes.test_commercial_agents import _create_payload, _tenant_registry


def _active_lead_agent(
    client: TestClient,
    headers: dict[str, str],
    db: Session,
) -> tuple[object, object, AgentDeployment, Contact]:
    tenant, installation, workspace, catalog = _tenant_registry(db)
    response = client.post(
        f"{settings.API_V1_STR}/commercial-agents/tenants/{tenant.id}/deployments",
        headers={**headers, "Idempotency-Key": f"agent-{uuid.uuid4()}"},
        json=_create_payload(installation, workspace, catalog),
    )
    assert response.status_code == 201
    deployment = db.get(AgentDeployment, uuid.UUID(response.json()["id"]))
    assert deployment is not None
    deployment.status = AgentDeploymentStatus.ACTIVE
    contact = Contact(
        workspace_id=workspace.id,
        email=f"lead-{uuid.uuid4().hex}@example.com",
        first_name="Ada",
        company="Analytical",
        phone="+15551234567",
        source_channel="web",
        tags_json=["chatbot-lead"],
        intent_json=["pricing"],
        consent_email=True,
        consent_voice=True,
        last_seen_at=datetime.now(timezone.utc),
    )
    db.add_all([deployment, contact])
    db.commit()
    return tenant, workspace, deployment, contact


def test_admin_publishes_policy_prepares_package_and_denies_unpaid_route(
    client: TestClient,
    superuser_token_headers: dict[str, str],
    db: Session,
) -> None:
    tenant, workspace, deployment, contact = _active_lead_agent(
        client, superuser_token_headers, db
    )
    prefix = f"{settings.API_V1_STR}/lead-preparation/tenants/{tenant.id}"
    policy_payload = {
        "workspace_id": workspace.id,
        "name": "ARA default scoring",
        "version": 1,
        "feature_weights": {
            "messaging_handoff": 35,
            "buyer_intent": 25,
            "voice_ready": 15,
            "company_known": 10,
            "recent_activity": 10,
            "email_available": 5,
        },
        "band_thresholds": {"HOT": 70, "WARM": 40},
        "freshness_windows": {"recent_activity_days": 30},
        "exclusion_rules": ["do_not_contact", "suppressed"],
    }
    dry_run = client.post(
        f"{prefix}/policies/dry-run",
        headers=superuser_token_headers,
        json={**policy_payload, "contact_id": str(contact.id)},
    )
    assert dry_run.status_code == 200
    assert dry_run.json()["score"] == 100

    create_headers = {
        **superuser_token_headers,
        "Idempotency-Key": f"policy-{uuid.uuid4()}",
    }
    created = client.post(
        f"{prefix}/policies", headers=create_headers, json=policy_payload
    )
    replay = client.post(
        f"{prefix}/policies", headers=create_headers, json=policy_payload
    )
    assert created.status_code == 201
    assert replay.json() == created.json()
    published = client.post(
        f"{prefix}/policies/{created.json()['id']}/publish",
        headers={
            **superuser_token_headers,
            "Idempotency-Key": f"publish-{uuid.uuid4()}",
        },
    )
    assert published.status_code == 200
    assert published.json()["status"] == "PUBLISHED"

    job_headers = {
        **superuser_token_headers,
        "Idempotency-Key": f"job-{uuid.uuid4()}",
    }
    job_payload = {
        "workspace_id": workspace.id,
        "deployment_id": str(deployment.id),
        "contact_id": str(contact.id),
        "policy_id": created.json()["id"],
        "event_key": f"contact:{contact.id}:manual",
    }
    job = client.post(f"{prefix}/jobs", headers=job_headers, json=job_payload)
    job_replay = client.post(f"{prefix}/jobs", headers=job_headers, json=job_payload)
    assert job.status_code == 201
    assert job_replay.json() == job.json()

    run_lead_preparation_batch(
        db,
        evidence_collector=lambda _: {
            "source_type": "contact_profile",
            "source_reference": f"contact:{contact.id}",
        },
    )
    packages = client.get(
        f"{prefix}/packages?workspace_id={workspace.id}",
        headers=superuser_token_headers,
    )
    assert packages.status_code == 200
    assert len(packages.json()) == 1
    package_id = packages.json()[0]["id"]
    approved = client.post(
        f"{prefix}/packages/{package_id}/approve",
        headers={
            **superuser_token_headers,
            "Idempotency-Key": f"approve-{uuid.uuid4()}",
        },
        json={"reason": "Sales review complete"},
    )
    denied_route = client.post(
        f"{prefix}/packages/{package_id}/route",
        headers={
            **superuser_token_headers,
            "Idempotency-Key": f"route-{uuid.uuid4()}",
        },
        json={"channel": "email"},
    )
    assert approved.status_code == 200
    assert approved.json()["review_state"] == "APPROVED"
    assert denied_route.status_code == 409
    assert "dependency" in denied_route.json()["detail"].lower()


def test_job_requires_idempotency_and_hides_cross_workspace_contact(
    client: TestClient,
    superuser_token_headers: dict[str, str],
    db: Session,
) -> None:
    tenant, workspace, deployment, contact = _active_lead_agent(
        client, superuser_token_headers, db
    )
    other = Contact(workspace_id=f"other-{uuid.uuid4().hex[:8]}", email="other@example.com")
    db.add(other)
    db.commit()
    payload = {
        "workspace_id": workspace.id,
        "deployment_id": str(deployment.id),
        "contact_id": str(other.id),
        "policy_id": str(uuid.uuid4()),
        "event_key": f"contact:{other.id}:manual",
    }
    url = f"{settings.API_V1_STR}/lead-preparation/tenants/{tenant.id}/jobs"

    missing = client.post(url, headers=superuser_token_headers, json=payload)
    hidden = client.post(
        url,
        headers={
            **superuser_token_headers,
            "Idempotency-Key": f"cross-{uuid.uuid4()}",
        },
        json=payload,
    )

    assert missing.status_code == 400
    assert hidden.status_code in {404, 409}


def test_operator_replays_dead_letter_and_records_outcome_without_policy_change(
    client: TestClient,
    superuser_token_headers: dict[str, str],
    db: Session,
) -> None:
    tenant, workspace, deployment, contact = _active_lead_agent(
        client, superuser_token_headers, db
    )
    policy = build_default_scoring_policy(
        tenant_id=tenant.id, workspace_id=workspace.id, version=1
    )
    db.add(policy)
    db.commit()
    job = enqueue_preparation_job(
        db,
        tenant_id=tenant.id,
        workspace_id=workspace.id,
        deployment_id=deployment.id,
        contact_id=contact.id,
        policy_id=policy.id,
        event_key=f"contact:{contact.id}:failed",
    )
    job.status = LeadPreparationJobStatus.DEAD_LETTER
    db.add(job)
    db.commit()
    prefix = f"{settings.API_V1_STR}/lead-preparation/tenants/{tenant.id}"

    report = client.get(
        f"{prefix}/operations/reconciliation?workspace_id={workspace.id}",
        headers=superuser_token_headers,
    )
    replay = client.post(
        f"{prefix}/jobs/{job.id}/replay",
        headers={
            **superuser_token_headers,
            "Idempotency-Key": f"replay-{uuid.uuid4()}",
        },
        json={"reason": "Evidence source recovered"},
    )
    outcome_headers = {
        **superuser_token_headers,
        "Idempotency-Key": f"outcome-{uuid.uuid4()}",
    }
    outcome_payload = {
        "workspace_id": workspace.id,
        "contact_id": str(contact.id),
        "policy_id": str(policy.id),
        "outcome_type": "MEETING_BOOKED",
        "outcome_reference": "calendar:event:456",
        "observed_at": datetime.now(timezone.utc).isoformat(),
    }
    outcome = client.post(
        f"{prefix}/outcomes", headers=outcome_headers, json=outcome_payload
    )
    outcome_replay = client.post(
        f"{prefix}/outcomes", headers=outcome_headers, json=outcome_payload
    )

    assert report.status_code == 200
    assert report.json()["dead_letters"] == 1
    assert replay.status_code == 200
    assert replay.json()["status"] == "PENDING"
    assert outcome.status_code == 201
    assert outcome_replay.json() == outcome.json()
    db.refresh(policy)
    assert policy.status == "PUBLISHED"
