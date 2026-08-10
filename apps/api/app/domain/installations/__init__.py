"""Native product installation identity primitives."""

from app.domain.installations.workload_identity import (
    WorkloadClaims,
    WorkloadIdentityError,
    WorkloadVerifier,
    body_sha256,
    create_workload_assertion,
)

__all__ = [
    "WorkloadClaims",
    "WorkloadIdentityError",
    "WorkloadVerifier",
    "body_sha256",
    "create_workload_assertion",
]
