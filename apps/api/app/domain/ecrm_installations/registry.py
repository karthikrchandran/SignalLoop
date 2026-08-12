"""Platform-provisioned eCRM installation destinations and secret references."""

from __future__ import annotations

from dataclasses import dataclass
from urllib.parse import urlsplit


@dataclass(frozen=True)
class InstallationEndpoint:
    identifier: str
    ecrm_cell_id: str
    ecrm_cell_key: str
    base_url: str


@dataclass(frozen=True)
class SecretReference:
    identifier: str
    ecrm_cell_id: str
    environment_name: str


class ProvisionedInstallationRegistry:
    """Immutable allowlist loaded from deployment-owned configuration."""

    def __init__(
        self,
        endpoints: dict[str, dict[str, str]],
        secret_references: dict[str, dict[str, str]],
    ) -> None:
        self._endpoints = {
            identifier: InstallationEndpoint(
                identifier=identifier,
                ecrm_cell_id=value["ecrm_cell_id"],
                ecrm_cell_key=value["ecrm_cell_key"],
                base_url=_validate_origin(value["base_url"]),
            )
            for identifier, value in endpoints.items()
        }
        self._secret_references = {
            identifier: SecretReference(
                identifier=identifier,
                ecrm_cell_id=value["ecrm_cell_id"],
                environment_name=_validate_environment_name(value["environment_name"]),
            )
            for identifier, value in secret_references.items()
        }

    def destination(
        self, endpoint_id: str, secret_reference_id: str
    ) -> tuple[InstallationEndpoint, SecretReference]:
        try:
            endpoint = self._endpoints[endpoint_id]
            secret_reference = self._secret_references[secret_reference_id]
        except KeyError as exc:
            raise LookupError("installation destination is not provisioned") from exc
        if endpoint.ecrm_cell_id != secret_reference.ecrm_cell_id:
            raise LookupError("installation destination is not provisioned")
        return endpoint, secret_reference

    def environment_allowlist(self) -> dict[str, str]:
        return {
            reference.identifier: reference.environment_name
            for reference in self._secret_references.values()
        }

    def rotation_secret(
        self,
        *,
        ecrm_cell_id: str,
        ecrm_cell_key: str,
        base_url: str,
        secret_reference_id: str,
    ) -> SecretReference:
        endpoint_is_still_provisioned = any(
            endpoint.ecrm_cell_id == ecrm_cell_id
            and endpoint.ecrm_cell_key == ecrm_cell_key
            and endpoint.base_url == base_url
            for endpoint in self._endpoints.values()
        )
        try:
            secret_reference = self._secret_references[secret_reference_id]
        except KeyError as exc:
            raise LookupError("installation destination is not provisioned") from exc
        if (
            not endpoint_is_still_provisioned
            or secret_reference.ecrm_cell_id != ecrm_cell_id
        ):
            raise LookupError("installation destination is not provisioned")
        return secret_reference


def _validate_origin(value: str) -> str:
    parsed = urlsplit(value)
    if (
        parsed.scheme != "https"
        or not parsed.hostname
        or parsed.username is not None
        or parsed.password is not None
        or parsed.path not in {"", "/"}
        or parsed.query
        or parsed.fragment
    ):
        raise ValueError("installation endpoint must be an HTTPS origin")
    return value.rstrip("/")


def _validate_environment_name(value: str) -> str:
    if not value or not value.replace("_", "").isalnum():
        raise ValueError("invalid provisioned environment name")
    return value
