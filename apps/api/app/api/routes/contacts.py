"""Contact management and timeline API endpoints."""

from __future__ import annotations

import json
import uuid
from datetime import datetime
from typing import Annotated

from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    HTTPException,
    Query,
    Request,
    UploadFile,
)
from sqlmodel import Session, select

from app.api.deps import CurrentUser, SessionDep, require_admin
from app.api.request_context import WorkspaceIdDep
from app.domain.audit.audit_events import (
    append_audit_event_to_session,
    audit_actor_role,
)
from app.domain.contacts.import_service import parse_csv, preview_rows
from app.domain.contacts.segment_service import matches_rule
from app.domain.shared_records import service as shared_record_service
from app.domain.timeline.timeline_service import (
    get_contact_timeline,
    get_timeline_event_detail,
)
from app.domain_models import (
    Campaign,
    Contact,
    ContactImportPublic,
    ContactPublic,
    ContactsPublic,
    ImportRowError,
    PreviewRow,
    SegmentOperator,
    SemanticError,
    TimelineEventDetailPublic,
    TimelinePagePublic,
)

router = APIRouter(prefix="/contacts", tags=["contacts"])
MAX_UPLOAD_SIZE_BYTES = 10 * 1024 * 1024

CONTACT_IMPORT_FIELDS = [
    "email",
    "firstName",
    "lastName",
    "company",
    "phone",
    "timezone",
]
CONTACT_REQUIRED_FIELDS = ["email"]
CONTACT_FIELD_ALIASES = {
    "email": ["email", "emailAddress", "email_address", "work_email"],
    "firstName": ["firstName", "first_name", "firstname", "first", "given_name"],
    "lastName": ["lastName", "last_name", "lastname", "last", "family_name"],
    "company": ["company", "companyName", "company_name", "account", "organization"],
    "phone": ["phone", "phoneNumber", "phone_number", "mobile", "mobile_phone"],
    "timezone": ["timezone", "timeZone", "time_zone", "tz"],
}


def _contact_public(contact: Contact) -> ContactPublic:
    """Convert a stored contact to the route's public response model."""
    return ContactPublic.model_validate(contact)


def _default_mapping(headers: list[str]) -> dict[str, str]:
    normalized = {header.lower(): header for header in headers}
    mapping: dict[str, str] = {}
    for field in CONTACT_IMPORT_FIELDS:
        source = ""
        for alias in CONTACT_FIELD_ALIASES[field]:
            if alias.lower() in normalized:
                source = normalized[alias.lower()]
                break
        mapping[field] = source
    return mapping


def _parse_mapping(headers: list[str], mapping_json: str | None) -> dict[str, str]:
    if not mapping_json:
        return _default_mapping(headers)
    try:
        raw = json.loads(mapping_json)
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Mapping must be valid JSON")
    if not isinstance(raw, dict):
        raise HTTPException(status_code=400, detail="Mapping must be a JSON object")
    available = set(headers)
    mapping: dict[str, str] = {}
    for field in CONTACT_IMPORT_FIELDS:
        source = raw.get(field, "")
        if source and not isinstance(source, str):
            raise HTTPException(
                status_code=400, detail=f"Mapping for {field} must be a string"
            )
        if source and source not in available:
            raise HTTPException(
                status_code=400,
                detail=f"Mapping contains unknown source column: {source}",
            )
        mapping[field] = source or ""
    return mapping


def _clean(value: object) -> str:
    return str(value or "").strip()


def _map_contact_row(row: dict[str, object], mapping: dict[str, str]) -> dict[str, str]:
    return {
        field: _clean(row.get(source, "")) if source else ""
        for field, source in mapping.items()
    }


def _validate_contact_rows(
    rows: list[dict[str, object]],
    mapping: dict[str, str],
) -> tuple[list[dict[str, str]], list[ImportRowError]]:
    missing_required = [
        field for field in CONTACT_REQUIRED_FIELDS if not mapping.get(field)
    ]
    errors: list[ImportRowError] = []
    if missing_required:
        for field in missing_required:
            errors.append(
                ImportRowError(
                    row_number=0,
                    column=field,
                    semantic_error=SemanticError.recipient_invalid,
                    message=f"Map a source column for {field} before importing contacts.",
                )
            )
        return [], errors

    valid_rows: list[dict[str, str]] = []
    seen_emails: set[str] = set()
    for index, row in enumerate(rows, start=1):
        mapped = _map_contact_row(row, mapping)
        row_errors: list[ImportRowError] = []
        email = mapped["email"].lower()
        if not email:
            row_errors.append(
                ImportRowError(
                    row_number=index,
                    column="email",
                    semantic_error=SemanticError.recipient_invalid,
                    message="Email is required for contact import.",
                )
            )
        elif "@" not in email:
            row_errors.append(
                ImportRowError(
                    row_number=index,
                    column="email",
                    semantic_error=SemanticError.recipient_invalid,
                    message="Email must contain @.",
                )
            )
        elif email in seen_emails:
            row_errors.append(
                ImportRowError(
                    row_number=index,
                    column="email",
                    semantic_error=SemanticError.recipient_invalid,
                    message="Duplicate email in this import.",
                )
            )

        if row_errors:
            errors.extend(row_errors)
            continue
        mapped["email"] = email
        mapped["timezone"] = mapped.get("timezone") or "UTC"
        seen_emails.add(email)
        valid_rows.append(mapped)
    return valid_rows, errors


def _contact_filter_row(contact: ContactPublic) -> dict[str, str]:
    return {
        "email": contact.email,
        "firstName": contact.first_name or "",
        "first_name": contact.first_name or "",
        "lastName": contact.last_name or "",
        "last_name": contact.last_name or "",
        "company": contact.company or "",
        "phone": contact.phone or "",
        "timezone": contact.timezone or "UTC",
    }


def contact_matches_rules(contact: ContactPublic, rules: list[dict[str, str]]) -> bool:
    row = _contact_filter_row(contact)
    return all(
        matches_rule(
            row.get(rule["field_name"]),
            SegmentOperator(rule["operator"]),
            rule["value"],
        )
        for rule in rules
    )


def _apply_contact_filters(
    contacts: list[ContactPublic],
    *,
    search: str | None = None,
    has_phone: bool | None = None,
    field_name: str | None = None,
    operator: SegmentOperator | None = None,
    value: str | None = None,
) -> list[ContactPublic]:
    filtered = contacts
    if search:
        needle = search.lower()
        filtered = [
            contact
            for contact in filtered
            if needle
            in " ".join(
                [
                    contact.email,
                    contact.first_name or "",
                    contact.last_name or "",
                    contact.company or "",
                    contact.phone or "",
                ]
            ).lower()
        ]
    if has_phone is not None:
        filtered = [contact for contact in filtered if bool(contact.phone) is has_phone]
    if field_name and operator and value is not None:
        rules = [{"field_name": field_name, "operator": operator.value, "value": value}]
        filtered = [
            contact for contact in filtered if contact_matches_rules(contact, rules)
        ]
    return filtered


def _upsert_contacts(
    session: Session,
    *,
    workspace_id: str,
    rows: list[dict[str, str]],
) -> tuple[int, int]:
    created = 0
    updated = 0
    for row in rows:
        email = row["email"].lower()
        company = row.get("company") or None
        account = None
        if company:
            account_key = shared_record_service.generate_account_key(company)
            account_id = uuid.uuid5(
                uuid.NAMESPACE_URL,
                f"emailvoice:account:{workspace_id}:{account_key}",
            )
            account = shared_record_service.upsert_shared_account(
                workspace_id=workspace_id,
                account_id=account_id,
                name=company,
                account_key=account_key,
                session=session,
            )

        contact_id = uuid.uuid5(
            uuid.NAMESPACE_URL,
            f"emailvoice:contact:{workspace_id}:{email}",
        )
        existing = shared_record_service.get_shared_contact(
            workspace_id=workspace_id,
            contact_id=contact_id,
            session=session,
        )
        shared_record_service.upsert_shared_contact(
            workspace_id=workspace_id,
            contact_id=contact_id,
            email=email,
            first_name=row.get("firstName") or None,
            last_name=row.get("lastName") or None,
            company=account.name if account else (company or (existing.company if existing else None)),
            phone=row.get("phone") or None,
            timezone=row.get("timezone") or "UTC",
            parent_id=account.id if account else (existing.account_id if existing else None),
            session=session,
        )
        if existing is None:
            created += 1
        else:
            updated += 1
    return created, updated


def _get_contact_or_404(
    session: Session,
    contact_id: uuid.UUID,
    workspace_id: str,
) -> ContactPublic:
    contact = shared_record_service.get_shared_contact(
        workspace_id=workspace_id,
        contact_id=contact_id,
    )
    if not contact:
        raise HTTPException(status_code=404, detail="Contact not found")
    return contact


def _get_campaign_or_404(
    session: Session,
    campaign_id: uuid.UUID,
    workspace_id: str,
) -> Campaign:
    campaign = session.exec(
        select(Campaign).where(
            Campaign.id == campaign_id,
            Campaign.workspace_id == workspace_id,
        )
    ).first()
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")
    return campaign


@router.get("/", response_model=ContactsPublic, dependencies=[Depends(require_admin)])
def read_contacts(
    session: SessionDep,
    workspace_id: WorkspaceIdDep,
    search: Annotated[str | None, Query(max_length=255)] = None,
    has_phone: Annotated[bool | None, Query()] = None,
    field_name: Annotated[str | None, Query(max_length=64)] = None,
    operator: Annotated[SegmentOperator | None, Query()] = None,
    value: Annotated[str | None, Query(max_length=255)] = None,
    skip: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
) -> ContactsPublic:
    """Return canonical contacts for the active workspace."""
    contacts = shared_record_service.list_shared_contacts(
        workspace_id=workspace_id,
        search=search,
        limit=min(skip + limit, 100),
    )
    filtered = _apply_contact_filters(
        contacts,
        search=search,
        has_phone=has_phone,
        field_name=field_name,
        operator=operator,
        value=value,
    )
    if has_phone is not None:
        filtered = [contact for contact in filtered if bool(contact.phone) is has_phone]
    return ContactsPublic(data=filtered[skip : skip + limit], count=len(filtered))


@router.post(
    "/import", response_model=ContactImportPublic, dependencies=[Depends(require_admin)]
)
async def import_contacts_to_pool(
    *,
    session: SessionDep,
    current_user: CurrentUser,
    workspace_id: WorkspaceIdDep,
    file: UploadFile = File(...),
    mapping_json: str | None = Form(default=None),
    commit: bool = Form(default=False),
) -> ContactImportPublic:
    """Preview or commit a CSV import into the canonical contact pool."""
    file_bytes = await file.read()
    if len(file_bytes) > MAX_UPLOAD_SIZE_BYTES:
        raise HTTPException(
            status_code=413, detail="CSV file too large. Maximum size is 10MB"
        )

    headers, rows = parse_csv(file_bytes)
    mapping = _parse_mapping(headers, mapping_json)
    valid_rows, errors = _validate_contact_rows(rows, mapping)
    created_count = 0
    updated_count = 0

    if commit and not errors:
        created_count, updated_count = _upsert_contacts(
            session, workspace_id=workspace_id, rows=valid_rows
        )
        append_audit_event_to_session(
            session,
            event_name="contacts.imported",
            workspace_id=workspace_id,
            actor_id=current_user.id,
            actor_role=audit_actor_role(current_user),
            resource_type="contact_import",
            resource_id=file.filename or "contacts.csv",
            payload={
                "source_file_name": file.filename or "contacts.csv",
                "total_rows": len(rows),
                "valid_rows": len(valid_rows),
                "created_count": created_count,
                "updated_count": updated_count,
                "mapped_fields": sorted(
                    field for field, source in mapping.items() if source
                ),
            },
        )
        session.commit()

    return ContactImportPublic(
        total_rows=len(rows),
        valid_rows=len(valid_rows),
        invalid_rows=len([error for error in errors if error.row_number > 0]),
        created_count=created_count,
        updated_count=updated_count,
        committed=commit and not errors,
        requires_mapping=any(error.row_number == 0 for error in errors),
        headers=headers,
        mapping=mapping,
        preview_rows=[
            PreviewRow(row_number=index + 1, data=row)
            for index, row in enumerate(preview_rows(valid_rows))
        ],
        errors=errors,
    )


@router.get(
    "/{contact_id}/timeline",
    response_model=TimelinePagePublic,
    dependencies=[Depends(require_admin)],
)
async def get_contact_timeline_route(
    contact_id: uuid.UUID,
    request: Request,
    session: SessionDep,
    workspace_id: WorkspaceIdDep,
    _current_user: CurrentUser,
    campaign_id: Annotated[uuid.UUID | None, Query()] = None,
    page: Annotated[int, Query(ge=1)] = 1,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    event_type: Annotated[str | None, Query(max_length=512)] = None,
    cursor: Annotated[str | None, Query(max_length=1024)] = None,
    from_dt: Annotated[datetime | None, Query(alias="from")] = None,
    to_dt: Annotated[datetime | None, Query(alias="to")] = None,
) -> TimelinePagePublic:
    """Return a paginated, chronologically sorted timeline for a contact.

    Aggregates from contact_state_history, contact_events, and routing_decisions.
    First unfiltered page is Redis-cached for 30 s (NFR2 / p95 < 3 s).
    """
    _get_contact_or_404(session, contact_id, workspace_id)
    if campaign_id:
        _get_campaign_or_404(session, campaign_id, workspace_id)
    return await get_contact_timeline(
        session=session,
        request=request,
        contact_id=contact_id,
        campaign_id=campaign_id,
        workspace_id=workspace_id,
        page=page,
        limit=limit,
        event_type=event_type,
        cursor=cursor,
        from_dt=from_dt,
        to_dt=to_dt,
    )


@router.get(
    "/{contact_id}/timeline/{event_id}",
    response_model=TimelineEventDetailPublic,
    dependencies=[Depends(require_admin)],
)
def get_contact_timeline_event(
    contact_id: uuid.UUID,
    event_id: str,
    session: SessionDep,
    workspace_id: WorkspaceIdDep,
    _current_user: CurrentUser,
) -> TimelineEventDetailPublic:
    """Return full explainability detail for one timeline entry."""
    _get_contact_or_404(session, contact_id, workspace_id)
    try:
        detail = get_timeline_event_detail(
            session=session,
            contact_id=contact_id,
            workspace_id=workspace_id,
            event_id=event_id,
        )
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid event_id format")
    if detail is None:
        raise HTTPException(status_code=404, detail="Timeline event not found")
    return detail
