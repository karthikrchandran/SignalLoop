from __future__ import annotations

import pytest

from app.domain.identity.transactions import (
    OidcTransaction,
    OidcTransactionStore,
    TransactionUnavailable,
)


class FakeRedis:
    def __init__(self) -> None:
        self.values: dict[str, str] = {}

    async def setex(self, key: str, ttl: int, value: str) -> None:
        self.values[key] = value

    async def get(self, key: str) -> str | None:
        return self.values.get(key)

    async def delete(self, key: str) -> None:
        self.values.pop(key, None)


@pytest.mark.anyio
async def test_oidc_transaction_preserves_verifier_and_is_one_use() -> None:
    store = OidcTransactionStore(FakeRedis(), ttl_seconds=300)
    transaction = OidcTransaction(
        transaction_id="tx-1",
        state_digest="state-digest",
        nonce_digest="nonce-digest",
        pkce_verifier="v" * 43,
        issuer="https://id.example.test",
        return_path="/",
    )
    await store.put(transaction)
    assert await store.consume("tx-1") == transaction
    assert await store.consume("tx-1") is None


@pytest.mark.anyio
async def test_oidc_transaction_store_fails_closed_when_redis_is_unavailable() -> None:
    class BrokenRedis:
        async def setex(self, *_args: object) -> None:
            raise RuntimeError("redis unavailable")

    store = OidcTransactionStore(BrokenRedis(), ttl_seconds=300)
    with pytest.raises(TransactionUnavailable):
        await store.put(
            OidcTransaction(
                transaction_id="tx-1",
                state_digest="state",
                nonce_digest="nonce",
                pkce_verifier="v" * 43,
                issuer="https://id.example.test",
                return_path="/",
            )
        )
