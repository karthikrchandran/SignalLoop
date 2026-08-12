"""Secret reference resolution at the installation connector boundary."""

from __future__ import annotations

import os
from typing import Protocol


class SecretResolver(Protocol):
    def resolve(self, reference: str) -> str:
        """Resolve an opaque reference or fail closed."""


class DictSecretResolver:
    """Deterministic resolver for local tests; values are never persisted."""

    def __init__(self, values: dict[str, str]) -> None:
        self._values = dict(values)

    def resolve(self, reference: str) -> str:
        try:
            value = self._values[reference]
        except KeyError as exc:
            raise LookupError("secret reference is unavailable") from exc
        if not value:
            raise LookupError("secret reference is unavailable")
        return value


class EnvSecretResolver:
    """Resolve only deployment-provisioned opaque references from the environment."""

    def __init__(self, environment_allowlist: dict[str, str]) -> None:
        self._environment_allowlist = dict(environment_allowlist)

    def resolve(self, reference: str) -> str:
        try:
            name = self._environment_allowlist[reference]
        except KeyError as exc:
            raise LookupError("secret reference is unavailable") from exc
        value = os.environ.get(name)
        if not value:
            raise LookupError("secret reference is unavailable")
        return value
