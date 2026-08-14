import uuid

import pytest
from pydantic import ValidationError

from app.models import UserPublic


def test_user_public_accepts_local_demo_identity() -> None:
    user = UserPublic.model_validate(
        {
            "id": uuid.uuid4(),
            "email": "admin@ara-global.demo.local",
            "is_active": True,
            "is_superuser": False,
            "role": "admin",
        }
    )

    assert user.email == "admin@ara-global.demo.local"


def test_user_public_rejects_malformed_identity() -> None:
    with pytest.raises(ValidationError):
        UserPublic.model_validate(
            {
                "id": uuid.uuid4(),
                "email": "not-an-email",
                "is_active": True,
                "is_superuser": False,
                "role": "admin",
            }
        )
