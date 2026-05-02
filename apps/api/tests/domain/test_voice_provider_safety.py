from __future__ import annotations

import asyncio
import logging

import pytest

from app.core.config import settings
from app.infrastructure.providers import deepgram_tts, groq_llm
from app.infrastructure.providers.deepgram_stt import DeepgramSTTAdapter
from app.infrastructure.providers.deepgram_tts import DeepgramTTSAdapter
from app.infrastructure.providers.errors import ProviderConfigurationError
from app.infrastructure.providers.groq_llm import GroqLLMAdapter


@pytest.mark.parametrize(
    ("setting_name", "factory"),
    [
        ("DEEPGRAM_API_KEY", DeepgramSTTAdapter),
        ("DEEPGRAM_API_KEY", DeepgramTTSAdapter),
        ("GROQ_API_KEY", GroqLLMAdapter),
    ],
)
def test_voice_provider_adapters_fail_fast_when_keys_are_missing(
    monkeypatch: pytest.MonkeyPatch,
    setting_name: str,
    factory,
) -> None:
    monkeypatch.setattr(settings, setting_name, "")

    with pytest.raises(ProviderConfigurationError, match=setting_name):
        factory()


class FakeGroqResponse:
    status_code = 401
    text = "raw groq body containing gsk_secret"


class FakeGroqClient:
    def __init__(self, *args, **kwargs) -> None:
        pass

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        pass

    async def post(self, *args, **kwargs) -> FakeGroqResponse:
        return FakeGroqResponse()


def test_groq_error_logging_excludes_raw_provider_body(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    monkeypatch.setattr(settings, "GROQ_API_KEY", "gsk_test")
    monkeypatch.setattr(groq_llm.httpx, "AsyncClient", FakeGroqClient)
    caplog.set_level(logging.ERROR)

    result = asyncio.run(
        GroqLLMAdapter().chat_completion(system_prompt="system", messages=[])
    )

    assert result == ""
    assert "status=401" in caplog.text
    assert "gsk_secret" not in caplog.text
    assert "raw groq body" not in caplog.text


class FakeTTSResponse:
    status_code = 403
    text = "raw deepgram body containing dg_secret"
    content = b""


class FakeTTSClient:
    def __init__(self, *args, **kwargs) -> None:
        pass

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        pass

    async def post(self, *args, **kwargs) -> FakeTTSResponse:
        return FakeTTSResponse()


def test_deepgram_tts_error_logging_excludes_raw_provider_body(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    monkeypatch.setattr(settings, "DEEPGRAM_API_KEY", "dg_test")
    monkeypatch.setattr(deepgram_tts.httpx, "AsyncClient", FakeTTSClient)
    caplog.set_level(logging.ERROR)

    result = asyncio.run(DeepgramTTSAdapter().synthesize("hello"))

    assert result == b""
    assert "status=403" in caplog.text
    assert "dg_secret" not in caplog.text
    assert "raw deepgram body" not in caplog.text