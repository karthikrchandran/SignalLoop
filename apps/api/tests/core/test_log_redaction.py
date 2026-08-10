from __future__ import annotations

import io
import logging

from app.core.log_redaction import SensitiveQueryRedactionFilter, redact_sensitive_query


def test_sensitive_callback_query_values_are_redacted() -> None:
    rendered = redact_sensitive_query(
        "/api/v1/voice/status?correlation=secret-correlation&token=secret-token&safe=ok"
    )

    assert "secret-correlation" not in rendered
    assert "secret-token" not in rendered
    assert "correlation=[REDACTED]" in rendered
    assert "token=[REDACTED]" in rendered
    assert "safe=ok" in rendered


def test_access_log_filter_redacts_format_arguments() -> None:
    output = io.StringIO()
    handler = logging.StreamHandler(output)
    handler.addFilter(SensitiveQueryRedactionFilter())
    logger = logging.getLogger("test.sensitive-query-redaction")
    logger.handlers = [handler]
    logger.propagate = False
    logger.setLevel(logging.INFO)

    logger.info(
        '127.0.0.1 - "POST %s HTTP/1.1" 200',
        "/api/v1/voice/status?correlation=do-not-log-me",
    )

    assert "do-not-log-me" not in output.getvalue()
    assert "correlation=[REDACTED]" in output.getvalue()
