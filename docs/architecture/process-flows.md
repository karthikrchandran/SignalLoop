# SignalLoop Process Flows

This document captures the main runtime flows that matter for operators and developers. The goal is to show where context is enforced, where state changes happen, and where asynchronous processing is expected to take over.

## 1. API Request Envelope

Every important mutation follows the same high-level envelope:

```mermaid
%%{init: {
  "theme": "base",
  "themeVariables": {
    "fontFamily": "Inter, -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif",
    "fontSize": "12px",
    "actorBkg": "#ffffff",
    "actorBorder": "#0f172a",
    "actorTextColor": "#0f172a",
    "actorLineColor": "#64748b",
    "signalColor": "#64748b"
  },
  "themeCSS": ".messageText { fill: #0f172a !important; stroke: #ffffff !important; stroke-width: 4px !important; paint-order: stroke fill !important; stroke-linejoin: round !important; } rect.actor { fill: #ffffff !important; stroke: #0f172a !important; stroke-width: 2px !important; } text.actor > tspan { fill: #0f172a !important; font-weight: bold; } line { stroke: #64748b !important; }"
}}%%
sequenceDiagram
    participant Client
    participant Middleware as Middleware Stack
    participant Route as FastAPI Route
    participant Authz as Casbin Authz
    participant Domain as Domain Service
    participant PG as PostgreSQL
    participant Audit as audit_events (PG)

    Client->>Middleware: HTTP request with workspace and idempotency headers
    Middleware->>Middleware: Generate or propagate request ID
    Middleware->>Route: Forward request with request.state.request_id
    Route->>Authz: Check role and permission
    Authz-->>Route: Allow or reject
    Route->>Domain: Execute use-case logic
    Domain->>PG: Persist transactional state
    Domain-->>Route: Return result
    Route->>Audit: Append audit event when applicable
    Route-->>Client: JSON response with X-Request-Id
```

## 2. Campaign Intake Flow

This is the most complete business flow in the repo today.

```mermaid
flowchart TD
    classDef default fill:#ffffff,stroke:#1e293b,stroke-width:2px,color:#0f172a;

    A["Operator creates campaign"] --> B["POST /campaigns"]
    B --> C["Campaign row saved"]
    C --> D["Audit event written to audit_events (PostgreSQL)"]
    D --> E["Operator uploads CSV"]
    E --> F["POST /campaigns/{id}/contacts/import"]
    F --> G["CSV parsed"]
    G --> H["Rows validated"]
    H --> I["Import summary saved"]
    I --> J["Staging rows stored"]
    J --> K["Operator submits field mapping"]
    K --> L["POST /campaigns/{id}/contacts/mapping"]
    L --> M["Mapping resolved"]
    M --> N["Rows remapped and revalidated"]
    N --> O["Preview returned"]
    O --> P["Operator creates segment"]
    P --> Q["Segment estimate computed from valid staged rows"]
    Q --> R["Operator assigns strategy and offer pack"]
```

## 3. Template Authoring And Publish Guardrail Flow

```mermaid
%%{init: {
  "theme": "base",
  "themeVariables": {
    "fontFamily": "Inter, -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif",
    "fontSize": "12px",
    "actorBkg": "#ffffff",
    "actorBorder": "#0f172a",
    "actorTextColor": "#0f172a",
    "actorLineColor": "#64748b",
    "signalColor": "#64748b"
  },
  "themeCSS": ".messageText { fill: #0f172a !important; stroke: #ffffff !important; stroke-width: 4px !important; paint-order: stroke fill !important; stroke-linejoin: round !important; } rect.actor { fill: #ffffff !important; stroke: #0f172a !important; stroke-width: 2px !important; } text.actor > tspan { fill: #0f172a !important; font-weight: bold; } line { stroke: #64748b !important; }"
}}%%
sequenceDiagram
    participant Lead
    participant API as Templates Route
    participant TokenSvc as Token Service
    participant Guardrails as Guardrail Service
    participant PG as PostgreSQL

    Lead->>API: Create or update template
    API->>TokenSvc: Validate token definitions
    TokenSvc-->>API: Valid or error list
    API->>PG: Save template, version, and tokens
    Lead->>API: Publish template version
    API->>Guardrails: Validate subject and content
    alt Violations found
        Guardrails-->>API: Violation list
        API->>PG: Save guardrail report
        API-->>Lead: 400 with violations
    else Compliant
        Guardrails-->>API: No violations
        API->>PG: Mark version published
        API-->>Lead: Published template
    end
```

## 4. Approval And Governance Flow

This flow captures how approval thresholds and governance controls are expected to work together.

```mermaid
flowchart TD
    classDef default fill:#ffffff,stroke:#1e293b,stroke-width:2px,color:#0f172a;

    subgraph OperatorLane ["1. Operator Actions"]
        O1["<b>Submit Approval Request</b><br/>POST /approvals/submit"]
    end

    subgraph SystemLane ["2. Automated Governance & Rules Engine"]
        S1{"<b>requires_approval(...)</b><br/>Policy threshold check"}
        S2["<b>Create Request Row</b><br/>policy_approval_requests (pending)"]
        S3[("<b>Append Audit Event</b><br/>audit_events: approval.submitted")]
    end

    subgraph AdminLane ["3. Administrative Review"]
        A1["<b>Review Request</b><br/>Inspect payload, context & rules"]
        A2["<b>Approve or Reject</b><br/>POST /approvals/{id}/approve or reject"]
    end

    O1 --> S1
    S1 -->|Approval Required| S2
    S1 -->|Auto-Approved| S3
    S2 --> S3
    S2 --> A1
    A1 --> A2
```

And the approval decision itself:

```mermaid
%%{init: {
  "theme": "base",
  "themeVariables": {
    "fontFamily": "Inter, -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif",
    "fontSize": "12px",
    "actorBkg": "#ffffff",
    "actorBorder": "#0f172a",
    "actorTextColor": "#0f172a",
    "actorLineColor": "#64748b",
    "signalColor": "#64748b"
  },
  "themeCSS": ".messageText { fill: #0f172a !important; stroke: #ffffff !important; stroke-width: 4px !important; paint-order: stroke fill !important; stroke-linejoin: round !important; } rect.actor { fill: #ffffff !important; stroke: #0f172a !important; stroke-width: 2px !important; } text.actor > tspan { fill: #0f172a !important; font-weight: bold; } line { stroke: #64748b !important; }"
}}%%
sequenceDiagram
    participant Operator
    participant API as Approvals Route
    participant Rules as Approval Service
    participant PG as PostgreSQL
    participant Audit as audit_events (PG)
    participant Admin

    Operator->>API: POST /approvals/submit
    API->>Rules: requires_approval(requested_action, payload)
    Rules-->>API: pending or auto-approved
    API->>PG: Save approval request
    API->>Audit: approval.submitted
    API-->>Operator: Approval request status

    Admin->>API: POST /approvals/{id}/approve or reject
    API->>PG: Update status, approver, resolved_at
    API->>Audit: approval.approved or approval.rejected
    API-->>Admin: Updated approval request
```

## 5. Policy Evaluation Flow

```mermaid
%%{init: {
  "theme": "base",
  "themeVariables": {
    "fontFamily": "Inter, -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif",
    "fontSize": "12px",
    "actorBkg": "#ffffff",
    "actorBorder": "#0f172a",
    "actorTextColor": "#0f172a",
    "actorLineColor": "#64748b",
    "signalColor": "#64748b"
  },
  "themeCSS": ".messageText { fill: #0f172a !important; stroke: #ffffff !important; stroke-width: 4px !important; paint-order: stroke fill !important; stroke-linejoin: round !important; } rect.actor { fill: #ffffff !important; stroke: #0f172a !important; stroke-width: 2px !important; } text.actor > tspan { fill: #0f172a !important; font-weight: bold; } line { stroke: #64748b !important; }"
}}%%
sequenceDiagram
    participant Operator
    participant API as Policies Route
    participant PG as PostgreSQL
    participant Engine as Policy Engine

    Operator->>API: POST /policies/evaluate
    API->>PG: Load active workspace policies
    API->>PG: Load campaign-bound policies when campaign_id is provided
    API->>Engine: evaluate_policies(...)
    alt Suppression or quiet-hours or cap rule blocks action
        Engine-->>API: allowed=false + semantic_error + reason_code
    else Allowed
        Engine-->>API: allowed=true
    end
    API-->>Operator: PolicyDecision
```

## 6. Pause And Resume Control Flow

```mermaid
flowchart TD
    classDef default fill:#ffffff,stroke:#1e293b,stroke-width:2px,color:#0f172a;

    A["Admin issues pause or resume request"] --> B["Controls route checks role and permission"]
    B --> C["Load or create global_control_state"]
    C --> D["Apply pause state or clear it"]
    D --> E["Optionally update campaign status"]
    E --> F["Return control-state response"]
    F --> G["Worker EnforcementGate consumes equivalent state to stop dequeueing"]
```

## 7. Multi-Channel Async Delivery Pipeline Flow

```mermaid
%%{init: {
  "theme": "base",
  "themeVariables": {
    "fontFamily": "Inter, -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif",
    "fontSize": "12px",
    "actorBkg": "#ffffff",
    "actorBorder": "#0f172a",
    "actorTextColor": "#0f172a",
    "actorLineColor": "#64748b",
    "signalColor": "#64748b"
  },
  "themeCSS": ".messageText { fill: #0f172a !important; stroke: #ffffff !important; stroke-width: 4px !important; paint-order: stroke fill !important; stroke-linejoin: round !important; } rect.actor { fill: #ffffff !important; stroke: #0f172a !important; stroke-width: 2px !important; } text.actor > tspan { fill: #0f172a !important; font-weight: bold; } line { stroke: #64748b !important; }"
}}%%
sequenceDiagram
    participant API
    participant PG as PostgreSQL
    participant Redis as Redis Queue / Lock
    participant Worker as Async Delivery Worker
    participant Provider as Comms Provider (SendGrid / Twilio / Vapi)
    participant Audit as audit_events (PG)

    API->>PG: Save contact progression and delivery intent
    API->>Redis: Enqueue work item with idempotency key
    Worker->>Redis: Dequeue eligible action and acquire lease lock
    Worker->>Provider: Send email or initiate outbound call
    Provider-->>Worker: Delivery result or call event
    Worker->>PG: Update action_queue and contact_progression
    Worker->>PG: Append contact_state_history
    Worker->>Audit: Append audit_events record
```

## 8. Swimlane View Of System Responsibilities

```mermaid
flowchart TD
    classDef default fill:#ffffff,stroke:#1e293b,stroke-width:2px,color:#0f172a;
    classDef store fill:#f8fafc,stroke:#1e293b,stroke-width:2px,color:#0f172a;

    subgraph Human ["1. Human Operators"]
        H1["Create Campaigns · Author Templates · Review Approvals · Pause/Resume"]
    end

    subgraph API ["2. API & Governance Layer"]
        A1["Validate Headers & OIDC Auth · Enforce Casbin RBAC · Persist State · Write Audit Events"]
    end

    subgraph Worker ["3. Async Worker Layer"]
        W1["Enforce Pause Gate · Dequeue Action Queue · Invoke Providers · Update Progression"]
    end

    subgraph Data ["4. Data & State Stores"]
        direction LR
        D1[("<b>PostgreSQL</b><br/>Operational State & Append-Only Audit Trail")]:::store
        D3[("<b>Redis</b><br/>Locks, Queues & Caps")]:::store
    end

    Human --> API
    API --> Data
    API --> Worker
    Worker --> Data
```

## 9. AI Lead Discovery & Waterfall Enrichment Flow

```mermaid
%%{init: {
  "theme": "base",
  "themeVariables": {
    "fontFamily": "Inter, -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif",
    "fontSize": "12px",
    "actorBkg": "#ffffff",
    "actorBorder": "#0f172a",
    "actorTextColor": "#0f172a",
    "actorLineColor": "#64748b",
    "signalColor": "#64748b"
  },
  "themeCSS": ".messageText { fill: #0f172a !important; stroke: #ffffff !important; stroke-width: 4px !important; paint-order: stroke fill !important; stroke-linejoin: round !important; } rect.actor { fill: #ffffff !important; stroke: #0f172a !important; stroke-width: 2px !important; } text.actor > tspan { fill: #0f172a !important; font-weight: bold; } line { stroke: #64748b !important; }"
}}%%
sequenceDiagram
    participant Operator as Operator / Cron
    participant API as Lead Discovery Route
    participant Gateway as Waterfall Gateway
    participant Resolver as Entity Resolver
    participant Scorer as AI 4-Pillar Scorer
    participant PG as PostgreSQL

    Operator->>API: POST /lead-discovery/search (ICP criteria)
    API->>Gateway: search_leads(criteria)
    Gateway->>Gateway: Query Apollo / Clay / Burkettopti / Sandbox
    Gateway-->>API: DiscoveredLeadDTO list
    API->>PG: Persist to discovered_leads & log query
    API-->>Operator: 200 Discovered Leads with Initial Scores

    Operator->>API: POST /lead-discovery/promote {lead_id}
    API->>Resolver: resolve_lead_entity(domain, company_name)
    Resolver->>PG: Match against existing accounts/contacts
    Resolver-->>API: MatchConfidence (EXACT, FUZZY, NEW)
    API->>PG: Create contacts row & update discovered_leads.is_promoted
    API->>PG: Enqueue welcome sequence into action_queue
    API->>PG: Append audit_events (lead_discovery.promoted)
    API-->>Operator: Promoted Contact ID & Enrollment Status
```

## 10. Governed Generative Proposal Generation Flow

```mermaid
%%{init: {
  "theme": "base",
  "themeVariables": {
    "fontFamily": "Inter, -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif",
    "fontSize": "12px",
    "actorBkg": "#ffffff",
    "actorBorder": "#0f172a",
    "actorTextColor": "#0f172a",
    "actorLineColor": "#64748b",
    "signalColor": "#64748b"
  },
  "themeCSS": ".messageText { fill: #0f172a !important; stroke: #ffffff !important; stroke-width: 4px !important; paint-order: stroke fill !important; stroke-linejoin: round !important; } rect.actor { fill: #ffffff !important; stroke: #0f172a !important; stroke-width: 2px !important; } text.actor > tspan { fill: #0f172a !important; font-weight: bold; } line { stroke: #64748b !important; }"
}}%%
sequenceDiagram
    participant Operator
    participant API as Proposal Agent Route
    participant Grounding as Grounding Engine
    participant LLM as LLM Synthesis (Groq/Ollama)
    participant PG as PostgreSQL
    participant eCRM as eCRM Lead-to-Cash System

    Operator->>API: POST /proposal-agent/generate
    API->>Grounding: gather_grounding_evidence(account_id)
    Grounding->>PG: Load account signals, meeting notes, offer packs
    Grounding-->>API: GroundingContext
    API->>LLM: synthesize_proposal(GroundingContext, pricing_rules)
    LLM-->>API: Generated Proposal JSON
    API->>PG: Persist proposal_generation_jobs (status: under_review)
    API-->>Operator: Reviewable Proposal Draft

    Operator->>API: POST /proposal-agent/{id}/approve
    API->>PG: Update status to approved & record reviewer
    API->>eCRM: Send signed commercial proposal event
    eCRM-->>API: 200 Proposal Acknowledged
    API->>PG: Record proposal_email_handoffs receipt
    API-->>Operator: Proposal Dispatched & Synchronized
```

## 11. Autonomous Calendar Scheduling & Booking Confirmation Flow

```mermaid
%%{init: {
  "theme": "base",
  "themeVariables": {
    "fontFamily": "Inter, -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif",
    "fontSize": "12px",
    "actorBkg": "#ffffff",
    "actorBorder": "#0f172a",
    "actorTextColor": "#0f172a",
    "actorLineColor": "#64748b",
    "signalColor": "#64748b"
  },
  "themeCSS": ".messageText { fill: #0f172a !important; stroke: #ffffff !important; stroke-width: 4px !important; paint-order: stroke fill !important; stroke-linejoin: round !important; } rect.actor { fill: #ffffff !important; stroke: #0f172a !important; stroke-width: 2px !important; } text.actor > tspan { fill: #0f172a !important; font-weight: bold; } line { stroke: #64748b !important; }"
}}%%
sequenceDiagram
    participant Prospect
    participant Worker as Calendar Scheduler Worker
    participant Provider as Cal Provider (Google/Outlook)
    participant PG as PostgreSQL

    Prospect->>Worker: Clicks verified booking link
    Worker->>PG: Validate scheduling_offers window & policy
    Worker->>Provider: Verify real-time slot availability
    Prospect->>Worker: Confirms time slot selection
    Worker->>Provider: Create calendar event & generate meeting URL
    Provider-->>Worker: external_event_id & confirmed_start
    Worker->>PG: Save calendar_booking_jobs & calendar_booking_receipts
    Worker->>PG: Transition contact_progression to booked
    Worker->>PG: Append audit_events (scheduling.booking_confirmed)
    Worker-->>Prospect: Booking Confirmation & ICS Invite
```

## Practical Takeaway

If you want one short summary of the product flow, it is this:

1. Humans configure and govern outreach through the API.
2. The API captures durable intent and audit evidence.
3. The worker layer executes async delivery, lead enrichment, proposal generation, and calendar bookings reliably.
4. Policy, approval, and pause controls ensure all autonomous actions remain strictly governable.
