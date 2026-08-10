"""Redact callback credentials from application and server access logs."""

from __future__ import annotations

import logging
import re
from typing import Any

_SENSITIVE_QUERY_VALUE = re.compile(
    r"(?i)([?&](?:correlation|token|media_token)=)[^&\s\"']+"
)


def redact_sensitive_query(value: str) -> str:
    """Remove secrets carried in unavoidable provider callback query values."""
    return _SENSITIVE_QUERY_VALUE.sub(r"\1[REDACTED]", value)


def _redact_value(value: Any) -> Any:
    return redact_sensitive_query(value) if isinstance(value, str) else value


class SensitiveQueryRedactionFilter(logging.Filter):
    """Redact sensitive query values before a logging handler formats a record."""

    def filter(self, record: logging.LogRecord) -> bool:
        record.msg = _redact_value(record.msg)
        if isinstance(record.args, tuple):
            record.args = tuple(_redact_value(arg) for arg in record.args)
        elif isinstance(record.args, dict):
            record.args = {
                key: _redact_value(value) for key, value in record.args.items()
            }
        return True


def install_sensitive_query_redaction() -> None:
    """Install an idempotent filter on application and Uvicorn loggers."""
    for logger_name in ("uvicorn.access", "uvicorn.error", "app"):
        target = logging.getLogger(logger_name)
        if not any(isinstance(item, SensitiveQueryRedactionFilter) for item in target.filters):
            target.addFilter(SensitiveQueryRedactionFilter())
