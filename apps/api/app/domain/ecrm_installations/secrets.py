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
    """Production-compatible reference resolver with an explicit env scheme."""

    def resolve(self, reference: str) -> str:
        prefix = "env://"
        if not reference.startswith(prefix):
            raise ValueError("only env:// secret references are supported")
        name = reference[len(prefix) :]
        if not name or not name.replace("_", "").isalnum():
            raise ValueError("invalid environment secret reference")
        value = os.environ.get(name)
        if not value:
            raise LookupError("secret reference is unavailable")
        return value
