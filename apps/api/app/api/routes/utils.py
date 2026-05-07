"""FastAPI router: ``utils`` endpoints."""

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse
from pydantic.networks import EmailStr
from sqlmodel import select
import anyio

from app.api.deps import get_current_active_superuser
from app.core.db import engine
from app.domain_models import HealthStatus
from app.models import Message
from app.utils import generate_test_email, send_email

router = APIRouter(prefix="/utils", tags=["utils"])


def _check_postgres_sync() -> bool:
    try:
        with engine.connect() as conn:
            conn.execute(select(1))
        return True
    except Exception:
        return False


@router.post(
    "/test-email/",
    dependencies=[Depends(get_current_active_superuser)],
    status_code=201,
)
def test_email(email_to: EmailStr) -> Message:
    """
    Test emails.
    """
    email_data = generate_test_email(email_to=email_to)
    send_email(
        email_to=email_to,
        subject=email_data.subject,
        html_content=email_data.html_content,
    )
    return Message(message="Test email sent")


@router.get("/health-check/", response_model=HealthStatus)
async def health_check(request: Request) -> HealthStatus:
    """Health check."""
    postgres = await anyio.to_thread.run_sync(_check_postgres_sync)

    redis = False
    redis_manager = getattr(request.app.state, "redis_manager", None)
    if redis_manager is not None:
        try:
            redis = await redis_manager.ping()
        except Exception:
            redis = False

    return HealthStatus(api=True, postgres=postgres, redis=redis)


@router.get("/live", include_in_schema=False)
async def liveness() -> dict[str, str]:
    """Kubernetes liveness probe — always 200 if the process is running."""
    return {"status": "ok"}


@router.get("/ready", include_in_schema=False)
async def readiness(request: Request) -> JSONResponse:
    """Kubernetes readiness probe — 200 only when all dependencies are reachable."""
    checks: dict[str, bool] = {}

    try:
        with engine.connect() as conn:
            conn.execute(select(1))
        checks["postgres"] = True
    except Exception:
        checks["postgres"] = False

    redis_manager = getattr(request.app.state, "redis_manager", None)
    try:
        checks["redis"] = await redis_manager.ping() if redis_manager else False
    except Exception:
        checks["redis"] = False

    all_healthy = all(checks.values())
    return JSONResponse(
        status_code=200 if all_healthy else 503,
        content={"status": "ready" if all_healthy else "not_ready", "checks": checks},
    )
