"""Package: ``api/routes``."""

from fastapi import APIRouter, Depends, Request
from pydantic.networks import EmailStr
from sqlmodel import select

from app.api.deps import get_current_active_superuser
from app.core.db import engine
from app.domain_models import HealthStatus
from app.models import Message
from app.utils import generate_test_email, send_email

router = APIRouter(prefix="/utils", tags=["utils"])


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
    postgres = True
    try:
        with engine.connect() as connection:
            connection.execute(select(1))
    except Exception:
        postgres = False

    redis = False
    redis_manager = getattr(request.app.state, "redis_manager", None)
    if redis_manager is not None:
        try:
            redis = await redis_manager.ping()
        except Exception:
            redis = False

    return HealthStatus(api=True, postgres=postgres, redis=redis)
