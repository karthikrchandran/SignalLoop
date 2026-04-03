"""Global rate-limiter configuration (SlowAPI / limits)."""
from __future__ import annotations

from slowapi import Limiter, _rate_limit_exceeded_handler  # noqa: F401 — re-exported
from slowapi.errors import RateLimitExceeded  # noqa: F401 — re-exported
from slowapi.middleware import SlowAPIMiddleware  # noqa: F401 — re-exported
from slowapi.util import get_remote_address

# Shared limiter instance — import this in route modules.
limiter = Limiter(key_func=get_remote_address, default_limits=["200/minute"])
