from app.domain.contacts.import_service import parse_csv, validate_rows
from app.domain.contacts.segment_service import estimate_segment, matches_rule
from app.domain_models import SegmentOperator


def test_parse_csv_and_validate_rows_mixed_valid_invalid() -> None:
    csv_bytes = (
        b"email,firstName,company,timezone\n"
        b"john@example.com,John,Acme,UTC\n"
        b",Jane,Globex,UTC\n"
    )

    headers, rows = parse_csv(csv_bytes)
    valid_rows, errors = validate_rows(headers, rows)

    assert headers == ["email", "firstName", "company", "timezone"]
    assert len(valid_rows) == 1
    assert valid_rows[0]["email"] == "john@example.com"
    assert len(errors) == 1
    assert errors[0].row_number == 2
    assert errors[0].column == "email"
    assert errors[0].semantic_error.value == "RECIPIENT_INVALID"


def test_validate_rows_requires_mapping_when_headers_do_not_match() -> None:
    headers = ["emailAddress", "first", "companyName", "tz"]
    rows = [{"emailAddress": "john@example.com", "first": "John", "companyName": "Acme", "tz": "UTC"}]

    valid_rows, errors = validate_rows(headers, rows)

    assert valid_rows == []
    assert len(errors) == 4
    assert all(error.row_number == 0 for error in errors)



def test_segment_operators_and_estimate_segment() -> None:
    rows = [
        {"company": "Acme Corp", "title": "VP Marketing", "region": "EMEA"},
        {"company": "Globex", "title": "Manager", "region": "NA"},
    ]

    assert matches_rule("Acme Corp", SegmentOperator.equals, "Acme Corp")
    assert matches_rule("Acme Corp", SegmentOperator.contains, "acme")
    assert matches_rule("NA", SegmentOperator.in_list, "APAC,EMEA,NA")
    assert matches_rule("VP Marketing", SegmentOperator.starts_with, "vp")

    rules = [
        {"field_name": "region", "operator": SegmentOperator.equals, "value": "EMEA"},
        {"field_name": "title", "operator": SegmentOperator.contains, "value": "Marketing"},
    ]
    assert estimate_segment(rows, rules) == 1
