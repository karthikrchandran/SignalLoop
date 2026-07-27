from __future__ import annotations

from unittest.mock import Mock

import pytest

from app.integrations.ecrm_workflow_events import EcrmWorkflowEventsClient


def test_emit_event_posts_workflow_payload() -> None:
    client = EcrmWorkflowEventsClient(base_url="https://ecrm.test", token="token-123")
    mock_request = Mock(return_value=Mock(status_code=201, json=lambda: {"ok": True}, text="{}"))

    import app.integrations.ecrm_workflow_events as module

    module.httpx.request = mock_request

    result = client.emit_event(
        {
            "sourceApp": "emailvoice",
            "sourceEventType": "meeting_booked",
            "entityType": "LEAD",
            "summary": "Meeting booked in EmailVoice",
            "payload": {"requestId": "req_1"},
        }
    )

    assert result == {"ok": True}
    mock_request.assert_called_once()
    kwargs = mock_request.call_args.kwargs
    assert kwargs["json"]["sourceEventType"] == "meeting_booked"
    assert kwargs["headers"]["Authorization"] == "Bearer token-123"
    assert mock_request.call_args.args[:2] == ("POST", "https://ecrm.test/api/workflow-events")


@pytest.mark.parametrize("status_code", [401, 403, 500])
def test_emit_event_raises_on_failed_response(status_code: int) -> None:
    client = EcrmWorkflowEventsClient(base_url="https://ecrm.test", token="token-123")
    mock_request = Mock(return_value=Mock(status_code=status_code, text="boom", json=lambda: {}))

    import app.integrations.ecrm_workflow_events as module

    module.httpx.request = mock_request

    with pytest.raises(Exception):
        client.emit_event({"sourceApp": "emailvoice", "sourceEventType": "meeting_booked", "entityType": "LEAD", "summary": "x"})
