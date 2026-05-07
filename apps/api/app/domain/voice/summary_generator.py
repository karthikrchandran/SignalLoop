"""Generate structured post-call summaries for team notification emails."""
from __future__ import annotations

import html
from dataclasses import dataclass
from datetime import datetime

from app.domain.voice.models import CallOutcome, CallSession


@dataclass
class CallSummary:
    """Summary row: call."""
    contact_name: str
    contact_company: str
    contact_email: str
    duration_seconds: int
    outcome: str
    transcript_preview: str
    unanswered_questions: list[str]
    scheduling_interest: bool
    recording_url: str
    subject: str
    html_body: str


def generate_summary(
    call_session: CallSession,
    *,
    contact_name: str,
    contact_company: str,
    contact_email: str,
) -> CallSummary:
    """Build a formatted summary from call session data."""
    outcome_label = call_session.outcome.value if call_session.outcome else "unknown"

    # Extract unanswered questions
    unanswered: list[str] = []
    if call_session.unanswered_questions:
        unanswered = call_session.unanswered_questions.get("questions", [])

    # Transcript preview (first 500 chars)
    transcript = call_session.transcript or ""
    preview = transcript[:500] + ("..." if len(transcript) > 500 else "")

    # Build subject
    if call_session.scheduling_interest:
        subject = f"[SCHEDULING] {contact_name} — interested"
    else:
        subject = f"[EngageHub] Call Summary — {contact_name}"

    # Build HTML body
    html = _build_html(
        contact_name=contact_name,
        contact_company=contact_company,
        contact_email=contact_email,
        duration=call_session.duration_seconds,
        outcome=outcome_label,
        transcript_preview=preview,
        unanswered=unanswered,
        scheduling_interest=call_session.scheduling_interest,
        recording_url=call_session.recording_url or "",
    )

    return CallSummary(
        contact_name=contact_name,
        contact_company=contact_company,
        contact_email=contact_email,
        duration_seconds=call_session.duration_seconds,
        outcome=outcome_label,
        transcript_preview=preview,
        unanswered_questions=unanswered,
        scheduling_interest=call_session.scheduling_interest,
        recording_url=call_session.recording_url or "",
        subject=subject,
        html_body=html,
    )


def _build_html(
    *,
    contact_name: str,
    contact_company: str,
    contact_email: str,
    duration: int,
    outcome: str,
    transcript_preview: str,
    unanswered: list[str],
    scheduling_interest: bool,
    recording_url: str,
) -> str:
    scheduling_banner = ""
    if scheduling_interest:
        scheduling_banner = '<div style="background:#22c55e;color:white;padding:12px;border-radius:4px;margin-bottom:16px;font-weight:bold;">SCHEDULING REQUESTED — This prospect expressed interest in a meeting</div>'

    unanswered_section = ""
    if unanswered:
        items = "".join(f"<li>{html.escape(q)}</li>" for q in unanswered)
        unanswered_section = f'<h3 style="color:#ef4444;">Unanswered Questions</h3><ul>{items}</ul>'

    recording_link = ""
    if recording_url:
        recording_link = f'<p><a href="{recording_url}">Listen to full recording</a></p>'

    minutes = duration // 60
    seconds = duration % 60

    return f"""<div style="font-family:sans-serif;max-width:600px;margin:0 auto;">
    <h2>Call Summary — {html.escape(contact_name)}</h2>
    {scheduling_banner}
    <table style="width:100%;border-collapse:collapse;margin-bottom:16px;">
        <tr><td style="padding:8px;border-bottom:1px solid #e5e7eb;"><strong>Contact</strong></td><td style="padding:8px;border-bottom:1px solid #e5e7eb;">{html.escape(contact_name)} ({html.escape(contact_email)})</td></tr>
        <tr><td style="padding:8px;border-bottom:1px solid #e5e7eb;"><strong>Company</strong></td><td style="padding:8px;border-bottom:1px solid #e5e7eb;">{html.escape(contact_company)}</td></tr>
        <tr><td style="padding:8px;border-bottom:1px solid #e5e7eb;"><strong>Duration</strong></td><td style="padding:8px;border-bottom:1px solid #e5e7eb;">{minutes}m {seconds}s</td></tr>
        <tr><td style="padding:8px;border-bottom:1px solid #e5e7eb;"><strong>Outcome</strong></td><td style="padding:8px;border-bottom:1px solid #e5e7eb;">{html.escape(outcome)}</td></tr>
    </table>
    {unanswered_section}
    <h3>Transcript Preview</h3>
    <pre style="background:#f9fafb;padding:12px;border-radius:4px;white-space:pre-wrap;">{html.escape(transcript_preview)}</pre>
    {recording_link}
</div>"""
