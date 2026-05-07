"""Request tracing and security headers middleware."""
from __future__ import annotations

from contextvars import ContextVar
from uuid import uuid4

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

request_id_var: ContextVar[str] = ContextVar("request_id", default="")


def get_request_id() -> str:
    """Return the correlation/request ID for the current async context."""
    return request_id_var.get("")


class RequestTracingMiddleware(BaseHTTPMiddleware):
    """Extract or generate a correlation ID and propagate it through the request."""

    async def dispatch(self, request: Request, call_next) -> Response:  # type: ignore[override]
        """Dispatch the incoming request."""
        request_id = (
            request.headers.get("X-Request-ID")
            or request.headers.get("X-Correlation-Id")
            or str(uuid4())
        )
        request_id_var.set(request_id)
        request.state.request_id = request_id

        response = await call_next(request)
        response.headers["X-Request-Id"] = request_id
        return response


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Add OWASP-recommended security headers to every response."""

    async def dispatch(self, request: Request, call_next) -> Response:  # type: ignore[override]
        """Dispatch the incoming request."""
        response = await call_next(request)
        response.headers.setdefault("X-Frame-Options", "DENY")
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("X-XSS-Protection", "1; mode=block")
        response.headers.setdefault(
            "Strict-Transport-Security",
            "max-age=31536000; includeSubDomains",
        )
        response.headers.setdefault(
            "Content-Security-Policy",
            "default-src 'self'",
        )
        response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
        return response
