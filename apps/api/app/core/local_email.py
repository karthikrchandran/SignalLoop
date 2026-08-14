"""Validation for user identities in the supported local runtime."""

import re
from typing import Annotated, Any

from pydantic import BeforeValidator, EmailStr, TypeAdapter

from app.core.config import settings

_LOCAL_DEMO_EMAIL = re.compile(
    r"^[A-Za-z0-9.!#$%&'*+/=?^_`{|}~-]+@(?:[A-Za-z0-9-]+\.)*demo\.local$"
)
_email_validator = TypeAdapter(EmailStr)


def validate_user_email(value: Any) -> str:
    """Accept normal email identities and the explicit local demo namespace."""
    if not isinstance(value, str):
        return _email_validator.validate_python(value)

    normalized = value.strip().lower()
    if settings.ENVIRONMENT == "local" and _LOCAL_DEMO_EMAIL.fullmatch(normalized):
        return normalized
    return str(_email_validator.validate_python(normalized))


LocalUserEmail = Annotated[str, BeforeValidator(validate_user_email)]
