from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

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

    def list_contacts(
        self,
        *,
        workspace_id: str,
        search: str | None,
        parent_public_id: uuid.UUID | None,
        limit: int,
    ) -> list[dict[str, Any]]:
        statement = select(PlatformSharedContact).where(
            PlatformSharedContact.workspace_id == workspace_id
        )
        if search:
            search_term = f"%{search.lower()}%"
            statement = statement.where(
                (PlatformSharedContact.email.ilike(search_term))
                | (PlatformSharedContact.display_name.ilike(search_term))
            )
        if parent_public_id is not None:
            parent_row_id = self._find_entity_id_by_public_id(
                workspace_id=workspace_id,
                entity_type="ACCOUNT",
                public_id=parent_public_id,
            )
            if parent_row_id is None:
                return []
            statement = statement.where(
                PlatformSharedContact.parent_account_id == parent_row_id
            )
        statement = statement.order_by(PlatformSharedContact.created_at.desc()).limit(
            limit
        )
        return [self._serialize_contact(row) for row in self.session.exec(statement).all()]

    def get_contact_by_public_id(
        self,
        *,
        workspace_id: str,
        public_id: uuid.UUID,
    ) -> dict[str, Any] | None:
        row_id = self._find_entity_id_by_public_id(
            workspace_id=workspace_id,
            entity_type="CONTACT",
            public_id=public_id,
        )
        if row_id is None:
            return None
        contact = self.session.get(PlatformSharedContact, row_id)
        if contact is None or contact.workspace_id != workspace_id:
            return None
        return self._serialize_contact(contact)

    def list_accounts(
        self,
        *,
        workspace_id: str,
        search: str | None,
        limit: int,
    ) -> list[dict[str, Any]]:
        statement = select(PlatformSharedAccount).where(
            PlatformSharedAccount.workspace_id == workspace_id
        )
        if search:
            search_term = f"%{search.lower()}%"
            statement = statement.where(
                PlatformSharedAccount.display_name.ilike(search_term)
            )
        statement = statement.order_by(PlatformSharedAccount.updated_at.desc()).limit(
            limit
        )
        return [self._serialize_account(row) for row in self.session.exec(statement).all()]

    def get_account_by_public_id(
        self,
        *,
        workspace_id: str,
        public_id: uuid.UUID,
    ) -> dict[str, Any] | None:
        row_id = self._find_entity_id_by_public_id(
            workspace_id=workspace_id,
            entity_type="ACCOUNT",
            public_id=public_id,
        )
        if row_id is None:
            return None
        account = self.session.get(PlatformSharedAccount, row_id)
        if account is None or account.workspace_id != workspace_id:
            return None
        return self._serialize_account(account)

    def count_contacts_for_account(
        self,
        *,
        workspace_id: str,
        account_public_id: uuid.UUID,
    ) -> int:
        return len(
            self.list_contacts(
                workspace_id=workspace_id,
                search=None,
                parent_public_id=account_public_id,
                limit=1000,
            )
        )

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

    def _list_external_links(
        self,
        *,
        workspace_id: str,
        entity_type: str,
        entity_id: uuid.UUID,
    ) -> list[PlatformExternalLink]:
        return self.session.exec(
            select(PlatformExternalLink).where(
                PlatformExternalLink.workspace_id == workspace_id,
                PlatformExternalLink.entity_type == entity_type,
                PlatformExternalLink.entity_id == entity_id,
            )
        ).all()

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

    def _serialize_contact(self, contact: PlatformSharedContact) -> dict[str, Any]:
        return {
            "id": self._public_id_for_entity(
                workspace_id=contact.workspace_id,
                entity_type="CONTACT",
                entity_id=contact.id,
            ),
            "workspace_id": contact.workspace_id,
            "account_id": self._public_id_for_entity(
                workspace_id=contact.workspace_id,
                entity_type="ACCOUNT",
                entity_id=contact.parent_account_id,
            )
            if contact.parent_account_id is not None
            else None,
            "email": contact.email,
            "first_name": None,
            "last_name": None,
            "company": None,
            "phone": contact.phone,
            "timezone": "UTC",
            "source_channel": None,
            "tags_json": [],
            "intent_json": [],
            "last_seen_at": None,
            "created_at": contact.created_at,
        }

    def _serialize_account(self, account: PlatformSharedAccount) -> dict[str, Any]:
        return {
            "id": self._public_id_for_entity(
                workspace_id=account.workspace_id,
                entity_type="ACCOUNT",
                entity_id=account.id,
            ),
            "workspace_id": account.workspace_id,
            "name": account.display_name,
            "account_key": account.external_key.rsplit(":", 1)[-1],
            "website_url": None,
            "industry": None,
            "status": account.status,
            "summary": None,
            "tags": [],
            "created_at": account.created_at,
            "updated_at": account.updated_at,
        }

    def _public_id_for_entity(
        self,
        *,
        workspace_id: str,
        entity_type: str,
        entity_id: uuid.UUID | None,
    ) -> uuid.UUID | None:
        if entity_id is None:
            return None

        links = self._list_external_links(
            workspace_id=workspace_id,
            entity_type=entity_type,
            entity_id=entity_id,
        )
        for link in links:
            if link.source_app == "emailvoice":
                try:
                    return uuid.UUID(link.source_record_id)
                except ValueError:
                    continue
        for link in links:
            if link.source_record_id:
                return uuid.uuid5(
                    uuid.NAMESPACE_URL,
                    f"emailvoice:{self._fallback_prefix(entity_type)}:{link.source_record_id}",
                )
        return uuid.uuid5(
            uuid.NAMESPACE_URL,
            f"emailvoice:{self._fallback_prefix(entity_type)}:{entity_id}",
        )

    def _find_entity_id_by_public_id(
        self,
        *,
        workspace_id: str,
        entity_type: str,
        public_id: uuid.UUID,
    ) -> uuid.UUID | None:
        emailvoice_link = self._get_external_link(
            workspace_id=workspace_id,
            entity_type=entity_type,
            source_app="emailvoice",
            source_record_id=str(public_id),
        )
        if emailvoice_link is not None:
            return emailvoice_link.entity_id

        model = (
            PlatformSharedContact if entity_type == "CONTACT" else PlatformSharedAccount
        )
        rows = self.session.exec(
            select(model).where(model.workspace_id == workspace_id)  # type: ignore[attr-defined]
        ).all()
        for row in rows:
            resolved = self._public_id_for_entity(
                workspace_id=workspace_id,
                entity_type=entity_type,
                entity_id=row.id,
            )
            if resolved == public_id:
                return row.id
        return None

    @staticmethod
    def _fallback_prefix(entity_type: str) -> str:
        return "shared-contact" if entity_type == "CONTACT" else "shared-account"
