# Story 2.3: Implement SendGrid Email Adapter

Status: ready-for-dev

## Story

As a backend engineer,
I want to integrate SendGrid for email sending and webhook processing,
so that the sequence engine can send emails and track delivery/engagement events.

## Acceptance Criteria

1. **Given** a SendRequest is created **When** the adapter sends via SendGrid v3 API **Then** the email is sent with correct from, to, subject, body, and tracking headers
2. **Given** the adapter includes an idempotency key **When** SendGrid receives duplicate requests **Then** only one email is sent
3. **Given** SendGrid returns 429 or 5xx **When** the adapter retries **Then** exponential backoff is applied (max 3 retries)
4. **Given** SendGrid fires webhook events **When** POST /api/v1/webhooks/sendgrid is called **Then** events are verified via HMAC signature and stored in EmailEvent table
5. **Given** a DELIVERED event arrives **When** it is processed **Then** the SendRequest status is updated to SENT
6. **Given** a BOUNCED event arrives **When** it is processed **Then** the contact's sequence is STOPPED and a hard_bounce signal is recorded
7. **Given** an UNSUBSCRIBED event arrives **When** it is processed **Then** the contact is added to the suppression list and sequence STOPPED
8. **Given** a REPLIED event or inbound parse arrives **When** it is processed **Then** the reply content is available for signal detection (Story 2.5)

## Tasks / Subtasks

- [ ] Task 1: Create apps/api/app/infrastructure/providers/sendgrid.py (AC: 1,2,3)
  - [ ] SendGridAdapter class with send_email(send_request) method
  - [ ] Include X-Idempotency-Key header
  - [ ] Set reply-to address for reply tracking
  - [ ] Exponential backoff on 429/5xx
- [ ] Task 2: Add SENDGRID_API_KEY and SENDGRID_WEBHOOK_SECRET to settings (AC: 1,4)
- [ ] Task 3: Create webhook handler route POST /api/v1/webhooks/sendgrid (AC: 4,5,6,7)
  - [ ] Verify HMAC-SHA256 signature
  - [ ] Parse event batch (SendGrid sends arrays of events)
  - [ ] Match events to SendRequest by provider_message_id
  - [ ] Write EmailEvent records
- [ ] Task 4: Implement event processing logic (AC: 5,6,7,8)
  - [ ] DELIVERED → update SendRequest.status = SENT
  - [ ] BOUNCED (type=bounce) → stop sequence, record signal
  - [ ] UNSUBSCRIBED → stop sequence, add to suppression
  - [ ] REPLIED/inbound → store for signal detection
- [ ] Task 5: Create suppression list table and check (AC: 7)
  - [ ] Suppression model: email, reason, created_at
  - [ ] Check suppression before sending
- [ ] Task 6: Write unit tests for adapter (mock SendGrid API) (AC: 1,2,3)
- [ ] Task 7: Write integration tests for webhook handler (AC: 4,5,6,7)

## Dev Notes

- SendGrid free tier: 100 emails/day — sufficient for MVP
- Webhook signature verification is critical for security — reject unsigned events
- Use httpx for async HTTP calls to SendGrid API
- Provider message ID from SendGrid response maps to SendRequest.provider_message_id

### References
- [Source: architecture.md#Section-8 — SendGrid integration boundary]
- [Source: architecture.md#Section-5 — Email send flow step 4]
- [Source: prd.md#FR16 — SendGrid email delivery]

## Dev Agent Record
### Agent Model Used
### Debug Log References
### Completion Notes List
### File List
