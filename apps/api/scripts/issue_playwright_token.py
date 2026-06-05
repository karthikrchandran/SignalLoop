from __future__ import annotations

from datetime import timedelta
import sys

from sqlalchemy import text
from sqlmodel import Session

from app.core.config import settings
from app.core.db import engine
from app.core.security import create_access_token


def main() -> int:
    email = settings.FIRST_SUPERUSER

    with Session(engine) as session:
        row = session.exec(
            text('SELECT id FROM "user" WHERE lower(email) = lower(:email) LIMIT 1'),
            params={"email": str(email)},
        ).first()

    if row is None:
        print(f"User not found for token issuance: {email}", file=sys.stderr)
        return 1

    token = create_access_token(
        row[0],
        expires_delta=timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES),
    )
    print(token)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())