from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, select

from app.domain.shared_records.models import (
    PlatformExternalLink,
    PlatformSharedAccount,
    PlatformSharedContact,
)


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


class PlatformSharedRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def upsert_account(
        self,
        *,
        workspace_id: str,
        external_key: str,
        display_name: str,
        source_app: str,
        source_record_id: str,
    ) -> PlatformSharedAccount:
        account = self._get_account_by_external_key(external_key)
        if account is None:
            account = self._insert_account(
                workspace_id=workspace_id,
                external_key=external_key,
                display_name=display_name,
            )
        self._validate_workspace_match(
            row_workspace_id=account.workspace_id,
            workspace_id=workspace_id,
            entity_label="account",
            external_key=external_key,
        )
        if account.display_name != display_name:
            account.display_name = display_name
            account.updated_at = _utc_now()

        self._upsert_link(
            entity_type="ACCOUNT",
            entity_id=account.id,
            workspace_id=workspace_id,
            source_app=source_app,
            source_record_id=source_record_id,
        )
        return account

    def upsert_contact(
        self,
        *,
        workspace_id: str,
        external_key: str,
        display_name: str,
        email: str,
        parent_account_id: uuid.UUID | None,
        source_app: str,
        source_record_id: str,
    ) -> PlatformSharedContact:
        contact = self._get_contact_by_external_key(external_key)
        if contact is not None:
            self._validate_workspace_match(
                row_workspace_id=contact.workspace_id,
                workspace_id=workspace_id,
                entity_label="contact",
                external_key=external_key,
            )
        self._validate_parent_account(
            workspace_id=workspace_id,
            parent_account_id=parent_account_id,
        )
        if contact is None:
            contact = self._insert_contact(
                workspace_id=workspace_id,
                external_key=external_key,
                display_name=display_name,
                email=email,
                parent_account_id=parent_account_id,
            )
        self._validate_workspace_match(
            row_workspace_id=contact.workspace_id,
            workspace_id=workspace_id,
            entity_label="contact",
            external_key=external_key,
        )
        if (
            contact.display_name != display_name
            or contact.email != email
            or contact.parent_account_id != parent_account_id
        ):
            contact.display_name = display_name
            contact.email = email
            contact.parent_account_id = parent_account_id
            contact.updated_at = _utc_now()

        self._upsert_link(
            entity_type="CONTACT",
            entity_id=contact.id,
            workspace_id=workspace_id,
            source_app=source_app,
            source_record_id=source_record_id,
        )
        return contact

    def _upsert_link(
        self,
        *,
        entity_type: str,
        entity_id: uuid.UUID,
        workspace_id: str,
        source_app: str,
        source_record_id: str,
    ) -> None:
        link = self._get_external_link(
            workspace_id=workspace_id,
            entity_type=entity_type,
            source_app=source_app,
            source_record_id=source_record_id,
        )
        if link is None:
            link = self._insert_or_get_existing(
                create_row=lambda: PlatformExternalLink(
                    entity_type=entity_type,
                    entity_id=entity_id,
                    workspace_id=workspace_id,
                    source_app=source_app,
                    source_record_id=source_record_id,
                ),
                get_existing=lambda: self._get_external_link(
                    workspace_id=workspace_id,
                    entity_type=entity_type,
                    source_app=source_app,
                    source_record_id=source_record_id,
                ),
            )
        elif link.entity_id != entity_id:
            raise ValueError(
                "source identity already maps to a different entity row"
            )
        link.entity_id = entity_id
        link.workspace_id = workspace_id
        self.session.flush()

    def _get_account_by_external_key(
        self,
        external_key: str,
    ) -> PlatformSharedAccount | None:
        return self.session.exec(
            select(PlatformSharedAccount).where(
                PlatformSharedAccount.external_key == external_key
            )
        ).first()

    def _get_contact_by_external_key(
        self,
        external_key: str,
    ) -> PlatformSharedContact | None:
        return self.session.exec(
            select(PlatformSharedContact).where(
                PlatformSharedContact.external_key == external_key
            )
        ).first()

    def _get_external_link(
        self,
        *,
        workspace_id: str,
        entity_type: str,
        source_app: str,
        source_record_id: str,
    ) -> PlatformExternalLink | None:
        return self.session.exec(
            select(PlatformExternalLink).where(
                PlatformExternalLink.workspace_id == workspace_id,
                PlatformExternalLink.entity_type == entity_type,
                PlatformExternalLink.source_app == source_app,
                PlatformExternalLink.source_record_id == source_record_id,
            )
        ).first()

    def _insert_account(
        self,
        *,
        workspace_id: str,
        external_key: str,
        display_name: str,
    ) -> PlatformSharedAccount:
        return self._insert_or_get_existing(
            create_row=lambda: PlatformSharedAccount(
                workspace_id=workspace_id,
                external_key=external_key,
                display_name=display_name,
            ),
            get_existing=lambda: self._get_account_by_external_key(external_key),
        )

    def _insert_contact(
        self,
        *,
        workspace_id: str,
        external_key: str,
        display_name: str,
        email: str,
        parent_account_id: uuid.UUID | None,
    ) -> PlatformSharedContact:
        return self._insert_or_get_existing(
            create_row=lambda: PlatformSharedContact(
                workspace_id=workspace_id,
                external_key=external_key,
                display_name=display_name,
                email=email,
                parent_account_id=parent_account_id,
            ),
            get_existing=lambda: self._get_contact_by_external_key(external_key),
        )

    def _insert_or_get_existing(self, *, create_row, get_existing):  # noqa: ANN001
        row = create_row()
        try:
            with self.session.begin_nested():
                self.session.add(row)
                self.session.flush()
                return row
        except IntegrityError:
            existing = get_existing()
            if existing is not None:
                return existing
            raise

    def _validate_parent_account(
        self,
        *,
        workspace_id: str,
        parent_account_id: uuid.UUID | None,
    ) -> None:
        if parent_account_id is None:
            return

        parent_account = self.session.get(PlatformSharedAccount, parent_account_id)
        if parent_account is None or parent_account.workspace_id != workspace_id:
            raise ValueError(
                "parent_account_id must reference an account in the same workspace"
            )

    def _validate_workspace_match(
        self,
        *,
        row_workspace_id: str,
        workspace_id: str,
        entity_label: str,
        external_key: str,
    ) -> None:
        if row_workspace_id != workspace_id:
            raise ValueError(
                f"{entity_label} external_key '{external_key}' already belongs to a different workspace"
            )
