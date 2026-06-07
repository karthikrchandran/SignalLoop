"""Module: ``db``."""

from sqlmodel import Session, create_engine, select

from app.core.config import settings

engine = create_engine(str(settings.SQLALCHEMY_DATABASE_URI))


# make sure all SQLModel models are imported (app.models) before initializing DB
# otherwise, SQLModel might fail to initialize relationships properly
# for more details: https://github.com/fastapi/full-stack-fastapi-template/issues/28


def init_db(session: Session) -> None:
    # Tables should be created with Alembic migrations
    # But if you don't want to use migrations, create
    # the tables un-commenting the next lines
    # from sqlmodel import SQLModel

    # This works because the models are already imported and registered from app.models
    # SQLModel.metadata.create_all(engine)

    # Deferred imports to break circular dependency:
    # db -> crud -> models -> audit_events -> db (engine)
    """Initialise db."""
    from app import crud  # noqa: PLC0415
    from app.core.security import get_password_hash, verify_password  # noqa: PLC0415
    from app.domain.workspaces.service import (  # noqa: PLC0415
        ensure_workspace_membership,
        role_for_user,
    )
    from app.models import User, UserCreate  # noqa: PLC0415

    user = session.exec(
        select(User).where(User.email == settings.FIRST_SUPERUSER)
    ).first()
    if not user:
        user_in = UserCreate(
            email=settings.FIRST_SUPERUSER,
            password=settings.FIRST_SUPERUSER_PASSWORD,
            is_superuser=True,
        )
        user = crud.create_user(session=session, user_create=user_in)
    else:
        verified, updated_password_hash = verify_password(
            settings.FIRST_SUPERUSER_PASSWORD,
            user.hashed_password,
        )
        if not verified:
            user.hashed_password = get_password_hash(settings.FIRST_SUPERUSER_PASSWORD)
            session.add(user)
        elif updated_password_hash:
            user.hashed_password = updated_password_hash
            session.add(user)

    ensure_workspace_membership(
        session,
        workspace_id=settings.DEFAULT_WORKSPACE_ID,
        user_id=user.id,
        role=role_for_user(user),
    )
    session.commit()
