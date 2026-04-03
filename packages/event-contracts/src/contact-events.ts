import type { AuditEnvelope } from "./index.js";

// ---------------------------------------------------------------------------
// Contact lifecycle events
// ---------------------------------------------------------------------------

export type ContactProgressedEvent = AuditEnvelope & {
  eventName: "contact.progressed";
  contactId: string;
  campaignId: string;
  fromState: string;
  toState: string;
  reason: string;
};

export type ActionQueuedEvent = AuditEnvelope & {
  eventName: "action.queued";
  actionId: string;
  contactId: string;
  campaignId: string;
  actionType: "send_email" | "make_call" | "send_sms";
  channel: "email" | "phone" | "sms";
  payload: Record<string, unknown>;
};

export type ProviderEventReceived = AuditEnvelope & {
  eventName: "provider.event.received";
  provider: "sendgrid" | "twilio" | "mailchimp" | "calendly";
  providerEventId: string;
  eventType: string;
  rawPayload: Record<string, unknown>;
  normalizedEvent: Record<string, unknown>;
};

// Union of all contact lifecycle events — use as the event bus payload type.
export type ContactLifecycleEvent =
  | ContactProgressedEvent
  | ActionQueuedEvent
  | ProviderEventReceived;
