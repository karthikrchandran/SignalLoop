---
title: SignalLoop Process Flows
description: Operational flows for API requests, campaign intake, policy approval, and future delivery processing.
author: Codex
date: 2026-04-02
---

# SignalLoop Process Flows

This document captures the main runtime flows that matter for operators and developers. The goal is to show where context is enforced, where state changes happen, and where asynchronous processing is expected to take over.

## 1. API Request Envelope

Every important mutation follows the same high-level envelope:

```mermaid
%%{init: {"theme": "base", "themeVariables": {"primaryColor": "#EFF6FF", "primaryTextColor": "#1F2937", "primaryBorderColor": "#1D4ED8", "lineColor": "#334155", "secondaryColor": "#F3F4F6", "secondaryTextColor": "#1F2937", "tertiaryColor": "#DBEAFE", "tertiaryTextColor": "#1E3A8A", "background": "#F9FAFB", "clusterBkg": "#FFFFFF", "clusterBorder": "#BFDBFE", "fontFamily": "Inter, Segoe UI, sans-serif"}}}%%
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
%%{init: {"theme": "base", "themeVariables": {"primaryColor": "#EFF6FF", "primaryTextColor": "#1F2937", "primaryBorderColor": "#1D4ED8", "lineColor": "#334155", "secondaryColor": "#F3F4F6", "secondaryTextColor": "#1F2937", "tertiaryColor": "#DBEAFE", "tertiaryTextColor": "#1E3A8A", "background": "#F9FAFB", "clusterBkg": "#FFFFFF", "clusterBorder": "#BFDBFE", "fontFamily": "Inter, Segoe UI, sans-serif"}}}%%
flowchart TD
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
%%{init: {"theme": "base", "themeVariables": {"primaryColor": "#EFF6FF", "primaryTextColor": "#1F2937", "primaryBorderColor": "#1D4ED8", "lineColor": "#334155", "secondaryColor": "#F3F4F6", "secondaryTextColor": "#1F2937", "tertiaryColor": "#DBEAFE", "tertiaryTextColor": "#1E3A8A", "background": "#F9FAFB", "clusterBkg": "#FFFFFF", "clusterBorder": "#BFDBFE", "fontFamily": "Inter, Segoe UI, sans-serif"}}}%%
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
%%{init: {"theme": "base", "themeVariables": {"primaryColor": "#EFF6FF", "primaryTextColor": "#1F2937", "primaryBorderColor": "#1D4ED8", "lineColor": "#334155", "secondaryColor": "#F3F4F6", "secondaryTextColor": "#1F2937", "tertiaryColor": "#DBEAFE", "tertiaryTextColor": "#1E3A8A", "background": "#F9FAFB", "clusterBkg": "#FFFFFF", "clusterBorder": "#BFDBFE", "fontFamily": "Inter, Segoe UI, sans-serif"}}}%%
flowchart LR
    subgraph OperatorLane["Operator"]
        O1["Submit approval request"]
    end

    subgraph SystemLane["System"]
        S1["requires_approval(...)"]
        S2["Create policy_approval_requests row"]
        S3["Write audit event"]
    end

    subgraph AdminLane["Admin"]
        A1["Review request"]
        A2["Approve or reject"]
    end

    O1 --> S1
    S1 -->|Approval not needed| S2
    S1 -->|Approval required| S2
    S2 --> S3
    S2 --> A1
    A1 --> A2
```

And the approval decision itself:

```mermaid
%%{init: {"theme": "base", "themeVariables": {"primaryColor": "#EFF6FF", "primaryTextColor": "#1F2937", "primaryBorderColor": "#1D4ED8", "lineColor": "#334155", "secondaryColor": "#F3F4F6", "secondaryTextColor": "#1F2937", "tertiaryColor": "#DBEAFE", "tertiaryTextColor": "#1E3A8A", "background": "#F9FAFB", "clusterBkg": "#FFFFFF", "clusterBorder": "#BFDBFE", "fontFamily": "Inter, Segoe UI, sans-serif"}}}%%
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
%%{init: {"theme": "base", "themeVariables": {"primaryColor": "#EFF6FF", "primaryTextColor": "#1F2937", "primaryBorderColor": "#1D4ED8", "lineColor": "#334155", "secondaryColor": "#F3F4F6", "secondaryTextColor": "#1F2937", "tertiaryColor": "#DBEAFE", "tertiaryTextColor": "#1E3A8A", "background": "#F9FAFB", "clusterBkg": "#FFFFFF", "clusterBorder": "#BFDBFE", "fontFamily": "Inter, Segoe UI, sans-serif"}}}%%
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
%%{init: {"theme": "base", "themeVariables": {"primaryColor": "#EFF6FF", "primaryTextColor": "#1F2937", "primaryBorderColor": "#1D4ED8", "lineColor": "#334155", "secondaryColor": "#F3F4F6", "secondaryTextColor": "#1F2937", "tertiaryColor": "#DBEAFE", "tertiaryTextColor": "#1E3A8A", "background": "#F9FAFB", "clusterBkg": "#FFFFFF", "clusterBorder": "#BFDBFE", "fontFamily": "Inter, Segoe UI, sans-serif"}}}%%
flowchart TD
    A["Admin issues pause or resume request"] --> B["Controls route checks role and permission"]
    B --> C["Load or create global_control_state"]
    C --> D["Apply pause state or clear it"]
    D --> E["Optionally update campaign status"]
    E --> F["Return control-state response"]
    F --> G["Worker EnforcementGate consumes equivalent state to stop dequeueing"]
```

## 7. Target Delivery Pipeline Flow

This flow is partially implemented in schema and scaffolding. It describes the intended runtime path signaled by the Epic 2 tables.

```mermaid
%%{init: {"theme": "base", "themeVariables": {"primaryColor": "#EFF6FF", "primaryTextColor": "#1F2937", "primaryBorderColor": "#1D4ED8", "lineColor": "#334155", "secondaryColor": "#F3F4F6", "secondaryTextColor": "#1F2937", "tertiaryColor": "#DBEAFE", "tertiaryTextColor": "#1E3A8A", "background": "#F9FAFB", "clusterBkg": "#FFFFFF", "clusterBorder": "#BFDBFE", "fontFamily": "Inter, Segoe UI, sans-serif"}}}%%
sequenceDiagram
    participant API
    participant PG as PostgreSQL
    participant Outbox as Outbox Publisher
    participant Worker
    participant Queue as Action Queue
    participant Provider as External Provider
    participant Audit as audit_events (PG)

    API->>PG: Save contact progression or delivery intent
    API->>PG: Insert outbox_events row in same transaction
    Outbox->>PG: Poll unpublished outbox rows
    Outbox->>Queue: Enqueue action work item
    Worker->>Queue: Dequeue eligible action
    Worker->>Provider: Send message or initiate provider action
    Provider-->>Worker: Delivery result or error
    Worker->>PG: Update action_queue and contact_progression
    Worker->>PG: Append contact_state_history
    Worker->>Audit: Append audit_events / timeline event
```

## 8. Swimlane View Of Current And Emerging Responsibilities

```mermaid
%%{init: {"theme": "base", "themeVariables": {"primaryColor": "#EFF6FF", "primaryTextColor": "#1F2937", "primaryBorderColor": "#1D4ED8", "lineColor": "#334155", "secondaryColor": "#F3F4F6", "secondaryTextColor": "#1F2937", "tertiaryColor": "#DBEAFE", "tertiaryTextColor": "#1E3A8A", "background": "#F9FAFB", "clusterBkg": "#FFFFFF", "clusterBorder": "#BFDBFE", "fontFamily": "Inter, Segoe UI, sans-serif"}}}%%
flowchart LR
    subgraph Human["Human Operators"]
        H1["Create campaigns"]
        H2["Author templates"]
        H3["Review approvals"]
        H4["Pause or resume activity"]
    end

    subgraph API["API Layer"]
        A1["Validate headers and auth"]
        A2["Enforce RBAC and permissions"]
        A3["Persist operational state"]
        A4["Write audit events"]
    end

    subgraph Worker["Worker Layer"]
        W1["Check pause gate"]
        W2["Dequeue actions"]
        W3["Invoke providers"]
        W4["Update progression and history"]
    end

    subgraph Data["Data Stores"]
        D1["PostgreSQL\n(operational + audit_events)"]
        D3["Redis"]
    end

    H1 --> A1
    H2 --> A1
    H3 --> A1
    H4 --> A1
    A1 --> A2
    A2 --> A3
    A3 --> D1
    A4 --> D1
    D1 --> W1
    W1 --> W2
    W2 --> W3
    W3 --> W4
    W4 --> D1
    W1 --> D3
```

## Practical Takeaway

If you want one short summary of the product flow, it is this:

1. Humans configure and govern outreach through the API.
2. The API captures durable intent and audit evidence.
3. The worker layer is being built to turn that intent into reliable outbound actions.
4. Policy, approval, and pause controls exist to make sure automation stays governable.
