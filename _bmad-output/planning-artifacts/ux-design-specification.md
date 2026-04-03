---
date: "2026-04-02"
documentPurpose: "UX specification for the EngageHub MVP — automated email sequences and AI voice calling"
primaryAudience:
  - product_designer
  - frontend_developer
  - qa_lead
secondaryAudience:
  - product_manager
  - solution_architect
  - revenue_leader
---

# EngageHub UX Design Specification

## 1. UX Goal

The EngageHub MVP should feel like a calm control tower for automated outreach execution. The user should always understand:

- what the system is doing right now
- why it is executing this action (which sequence step, which campaign)
- what contacts are progressing and where
- what happened on each call or email interaction
- what to do when a contact needs attention

The UX must support marketing operations admins and revenue leaders first. Clarity and confidence in system execution matter more than flexibility or advanced customization.

## 2. Primary Experience Principles

1. Show execution in real time — emails sent, calls made, replies detected, signals surfaced.
2. Make the main experience web-first and responsive for tablet and desktop operators.
3. Make setup faster than manual outreach coordination — define sequence, upload script, upload contacts, activate.
4. Surface contact outcomes early and make response actions obvious (call this contact, send demo email, pause sequence).
5. Show one story across campaign → email sequence → voice call → signal → follow-up action.

## 3. Primary Users

### Marketing Operations Admin

Needs to create email sequences with different content per step, upload voice scripts, manage contact lists, launch campaigns, and adjust delays or script content without developer help.

### Revenue Operations Manager / Demand Gen Leader

Needs a consolidated view of email and call activity, signal detection progress, follow-up actions triggered, and quick pause/resume controls for authorized users.

### Sales Team Member (Secondary)

Receives post-call email summaries with unanswered questions and scheduling requests after each AI voice call — does not enter the admin interface regularly.

## 4. MVP UX Scope

### Included

- Responsive web admin experience (desktop-first, tablet/mobile support)
- Campaign setup with sequence assignment and script assignment
- Contact intake through CSV upload and field mapping
- Email sequence builder with multi-step configuration
- Voice script management with Q&A section preview
- Automated email sequence execution with timing
- AI voice calling with call outcome tracking
- Call review screen with recording playback and transcript
- Sequence progress monitor showing contact state per step
- Operations dashboard with email and call metrics
- Signal detection and automated follow-up actions
- Post-call email notifications to the team

### Not included in MVP

- Native mobile app
- Advanced analytics and A/B testing
- CRM integration
- Calendar bridge or formal booking workflow
- Template approval workflow
- Complex role-based governance (Phase 2)
- Multi-language voice support (Phase 2)
- Custom ML scoring models

## 5. Core Screens

### 5.1 Campaign Setup

**Purpose**: Help admins create a campaign, assign email sequences, assign voice scripts, and upload contacts safely.

**Required elements**:

- Campaign name, description, and status (Draft, Active, Paused, Completed)
- Campaign type selection (Email + Voice, Email Only, Voice Only)
- Email sequence selection (dropdown, allows change before activation)
- Voice script selection (dropdown, allows change before activation)
- Contact audience source (CSV upload, record count preview)
- Activation confirmation (shows which sequence, which script, how many contacts)
- Activation controls (Start, Schedule for later, Save draft)

**Interaction pattern**:

1. Admin enters campaign name and selects a type
2. Admin selects an existing sequence from a dropdown
3. Admin selects a script from a dropdown
4. Admin uploads CSV or selects existing contact list
5. System shows preview of what will be activated (e.g., "Send 3-step email sequence to 200 contacts, then make calls on step completion using script 'Cold Call Q&A v2'")
6. Admin confirms activation
7. System updates campaign status to Active and begins execution

**Visual guidance**:

- Use a hero button for "Activate Campaign" when all required selections are made
- Disable the activation button if any required field is missing, with clear explanation
- Show a summary card of selected sequence, script, and contact count before final activation

---

### 5.2 Contact Intake and Validation

**Purpose**: Make CSV import safe and understandable; separate invalid rows from accepted ones.

**Required elements**:

- Upload area (drag-and-drop or file picker)
- CSV template download (pre-built template with required columns)
- Field mapping step (map CSV columns to system fields: First Name, Last Name, Email, Phone, etc.)
- Invalid-row summary with error types (e.g., "Missing email", "Invalid phone format", "Duplicate contact")
- Accepted-row summary with count and preview of first 10 rows
- Clear next step: "Add these X contacts to campaign?" with confirmation button

**Interaction pattern**:

1. Admin uploads CSV file
2. System parses file and attempts auto-mapping of columns
3. Admin confirms or corrects field mappings
4. System validates each row
5. System displays two lists: valid rows (accept) and invalid rows (reject with reasons)
6. Admin can download invalid-row report for correction
7. Admin confirms "Import these X rows" — system adds contacts to campaign or staging area

**Visual guidance**:

- Show success state for valid rows in green
- Show error state for invalid rows in red with specific error message per row
- Allow admin to download a CSV template matching exactly the required columns
- Provide a summary count at the top: "X rows valid, Y rows need correction"

---

### 5.3 Sequence Builder

**Purpose**: Help admins create multi-step email sequences with different content per step and configurable delays.

**Required elements**:

- Sequence name and status (Draft, Published, Active in campaigns)
- Step list (add, reorder, edit, delete steps)
- Per-step configuration:
  - Step order (1, 2, 3, etc.)
  - Delay from previous step in days (0 for immediate, 3 for 3 days later)
  - Email subject line
  - Email body / template preview
  - Optional: personalization tokens (first name, company, etc.)
- Step reordering (drag-and-drop or arrow buttons)
- Preview mode (show what contact will see for each step)
- Save and publish controls

**Interaction pattern**:

1. Admin creates new sequence or edits existing one
2. Admin adds first step: selects or writes subject, writes/pastes email body
3. Admin adds step 2: sets delay (e.g., "Send 3 days after step 1"), writes subject and body
4. Admin continues adding steps (typical: 3–5 steps)
5. Admin can reorder steps by dragging or using arrow buttons
6. Admin previews full sequence before publishing
7. Admin saves as Draft or publishes (Published sequences can be assigned to campaigns)

**Visual guidance**:

- Use a vertical timeline layout showing step 1, arrow, "delay 3 days", step 2, arrow, etc.
- Show step number and delay prominently for each card
- Highlight the current step in editing mode
- Show a "Preview as contact" button that displays what the sequence looks like from recipient's perspective
- Use a green "Publish" button when sequence is complete; gray out "Publish" if required fields are missing

---

### 5.4 Script Management

**Purpose**: Allow admins to upload, edit, and preview voice scripts with Q&A sections formatted for the AI voice assistant.

**Required elements**:

- Script name and version (e.g., "Cold Call Q&A v1", "Cold Call Q&A v2")
- Script status (Draft, Published, Active in campaigns)
- Script upload area (text or file upload)
- Script content editor (editable text area)
- Q&A section parser (displays questions and answers as distinct sections for preview)
- Knowledge base preview (formatted display of all Q&A pairs)
- Opening pitch section (what the AI says when the prospect answers)
- Fallback section (what the AI says for unknown questions)
- Scheduling question (what the AI asks about scheduling a call with sales)
- Save and publish controls

**Interaction pattern**:

1. Admin creates new script or edits existing one
2. Admin writes or pastes script content (plain text or markdown format with Q&A sections marked as `Q: ... A: ...`)
3. System parses script and extracts opening pitch, Q&A pairs, fallback, and scheduling question
4. Admin previews the parsed Q&A knowledge base
5. Admin can edit individual Q&A pairs inline if needed
6. Admin saves as Draft or publishes
7. Published scripts can be assigned to campaigns

**Script format** (plain text with simple markers):

```
Opening Pitch:
Hi [first_name], this is [agent_name] from [company]. I'm calling about [campaign_offer]. Do you have 30 seconds?

Q: What is your product?
A: EngageHub automates B2B outreach with email sequences and AI voice calls.

Q: How much does it cost?
A: Pricing starts at [price]. I can connect you with our team for a detailed quote.

Q: Do you handle multi-language campaigns?
A: We currently support English. Multi-language is planned for Q3.

Fallback:
I'll make a note of that and have our team follow up with you via email. Is [email] the best way to reach you?

Scheduling Question:
Would you be open to a quick 15-minute call with our sales team next week? What day works best for you?
```

**Visual guidance**:

- Show Q&A pairs in a structured list with "Q:" and "A:" labels clearly separated
- Allow inline edit for each Q&A pair with a pencil icon
- Show a "Preview as AI" button that simulates how the AI will use this script
- Highlight syntax errors if script is malformed (missing A: after Q:, etc.)

---

### 5.5 Call Log

**Purpose**: Let admins review all AI voice calls, their outcomes, recordings, transcripts, and unanswered questions.

**Required elements**:

- Call list (table or scrollable list) with columns:
  - Contact name and phone
  - Call date/time
  - Call outcome (Answered, Voicemail, No answer, Busy, Failed)
  - Duration (if answered)
  - Signal result (Positive, Neutral, Negative, Unknown)
  - Scheduling request (Yes/No)
  - Unanswered question count
  - Action buttons (Play recording, View transcript, Review unanswered questions, Trigger follow-up)

- Call detail view (side panel or full screen):
  - Contact info and campaign name
  - Call date, time, duration, outcome
  - Audio player for call recording
  - Full transcript (if available) with timestamps
  - List of unanswered questions the prospect asked
  - Signal classification and reason
  - Scheduling interest (if expressed)
  - Manual follow-up action buttons (Send demo email now, Schedule call with sales, Pause sequence, etc.)

**Interaction pattern**:

1. Admin views Call Log from main navigation
2. Admin sees list of recent calls (sorted by date, newest first)
3. Admin filters by outcome, date range, campaign, or signal result
4. Admin clicks a call row to open side panel or full view
5. Admin plays recording, reads transcript, sees unanswered questions
6. Admin can manually trigger follow-up actions if needed (send demo email, flag for sales team, pause sequence)

**Visual guidance**:

- Use color to indicate outcome: Green for Answered, Yellow for Voicemail, Red for No answer/Failed, Gray for Busy
- Show call duration in minutes:seconds format (e.g., "4:23")
- Show unanswered question count as a badge (red if > 0)
- Play audio inline with a standard HTML5 audio player
- Display transcript with timestamps in a scrollable area
- Highlight unanswered questions in a separate collapsible section

---

### 5.6 Sequence Monitor

**Purpose**: Show admins how contacts are progressing through email sequence steps, which are paused, and which have triggered follow-up actions.

**Required elements**:

- Sequence selection (dropdown or tabs for active sequences)
- Step progress view showing:
  - Step number, subject, delay, and scheduled send date
  - Progress bar showing percentage of contacts who reached this step
  - Contact count at each step (e.g., "142 of 200 contacts")
  - Step status indicators (Sent, In progress, Scheduled, Paused on this step)

- Contact state breakdown:
  - Total in sequence: 200
  - Completed all steps: 45
  - Paused (positive signal detected): 12
  - Paused (reply received): 8
  - In progress: 135
  - Failed/unsubscribed: 5
  - Not started yet: 0

- Triggered follow-up actions view:
  - Shows contacts who have signals and triggered follow-up calls or demo emails
  - Contact name, signal type, follow-up action, status (Pending, Scheduled, Completed)

- Detailed contact list (optional detail panel):
  - Shows individual contact state: which step they're on, when next email is scheduled
  - Manual pause/resume controls per contact
  - Quick action to view contact timeline

**Interaction pattern**:

1. Admin opens Sequence Monitor from main navigation
2. Admin selects a sequence from dropdown
3. System displays progress across all steps for that sequence
4. Admin sees contact counts at each stage
5. Admin can select a step to see all contacts at that step
6. Admin can view contact detail to see individual timeline
7. Admin can manually pause a contact or trigger follow-up actions if campaign logic needs override

**Visual guidance**:

- Use a horizontal timeline showing each step in order, with progress bars showing contact flow
- Show step delay prominently (e.g., "→ 3 days → Step 2")
- Use a donut chart or progress bars to show status breakdown
- Highlight paused contacts in yellow, failed in red, completed in green
- Show follow-up actions in a separate section with action badges (blue for "Call scheduled", green for "Demo email sent")

---

### 5.7 Operations Dashboard

**Purpose**: Give admins a consolidated view of all campaign activity — emails sent, calls made, signals detected, and follow-up actions triggered.

**Required elements**:

- Key metrics (cards at top):
  - Emails sent (today, this week, total)
  - Email open rate (%)
  - Email reply rate (%)
  - Calls made (today, remaining in daily cap)
  - Call answer rate (%)
  - Calls with positive signal (%)
  - Scheduling requests generated
  - Sequences paused on signal

- Activity charts (time-series graphs):
  - Emails sent over time (last 7 days or last 30 days)
  - Calls made over time with answer rate overlay
  - Signal detection rate over time
  - Follow-up actions triggered over time

- Active campaigns summary (table):
  - Campaign name
  - Status (Active, Paused, Completed)
  - Contacts sent to / total in campaign
  - Sequences assigned / scripts assigned
  - Email send progress
  - Call progress
  - Signal summary
  - Pause/resume controls

- Recent events feed (chronological log):
  - Contact X replied to step 2 → sequence paused, follow-up call queued
  - Contact Y completed all steps
  - Contact Z answered call → positive signal, demo email queued
  - System reached daily call cap at 14:32 (50 calls)
  - Campaign "Q2 Leads" activated, 200 contacts

- Quick action controls:
  - Pause all / Resume all
  - View detailed metrics (drill-down)
  - Export report (CSV)

**Interaction pattern**:

1. Admin opens Dashboard from main navigation
2. System displays key metrics and current activity
3. Admin can select a campaign to focus on that campaign's metrics
4. Admin can select a date range to view metrics for past periods
5. Admin can pause/resume campaigns or individual contacts as needed
6. Admin can export a report for leadership review

**Visual guidance**:

- Use a card-based layout for key metrics with large numbers and color coding (green for on-track, yellow for warning, red for issues)
- Show line charts for time-series data (emails/calls per day)
- Use a table for active campaigns with sortable columns
- Show the recent events feed as a timeline with icons for email, call, signal, etc.
- Highlight any system alerts or warnings prominently (e.g., "Daily call cap reached", "High bounce rate on sequence step 2")

---

## 6. Interaction Model

### Default Navigation

The primary navigation should support:

- Dashboard (home, key metrics and active campaigns)
- Campaigns (create, edit, activate, view details)
- Contacts (upload, validate, view in campaign)
- Sequences (create, edit, publish, preview)
- Scripts (create, edit, publish, preview)
- Call Log (review calls, transcripts, recordings, outcomes)
- Sequence Monitor (view progression, pause/resume contacts)
- Operations (consolidated activity and metrics)
- Settings (team, integrations, quiet hours, daily caps)

### Preferred Detail Pattern

The MVP should use a simple context ladder:

1. Summary list or table with key information visible
2. Inline side panel or modal for details without losing context
3. Full detail view or editor only when the user is actively configuring something

This helps the interface stay fast and readable for operators managing campaigns in real time.

---

## 7. Visual and Content Guidance

### Tone

Use plain language focused on action and outcome. Prefer:

- "Email sent successfully to 142 contacts"
- "Call answered — prospect interested in demo"
- "Sequence paused on positive reply"
- "Positive signal detected, follow-up call queued"
- "Voicemail left — system will try again tomorrow"
- "3 unanswered questions to review"

Avoid:

- Raw provider errors ("SMTP Delivery Failure: 550 5.1.2") — show user-friendly summary instead ("Email failed to 3 recipients, check addresses")
- Technical terminology ("Media Stream connection lost", "WebSocket timeout")
- Database or queue references ("Event 12847 enqueued", "State machine transition pending")

### Status Communication

Use a small number of clear states mapped to user actions:

**Email sequence statuses**:
- Active — currently sending
- Paused — on hold (human paused or signal triggered pause)
- Completed — all steps sent to this contact
- Failed — bounce or invalid address
- Waiting for delay — next step scheduled for [date/time]

**Call statuses**:
- Queued — waiting to be placed
- In progress — call currently happening
- Answered — prospect picked up
- Voicemail — left message
- No answer — no pickup, no voicemail
- Failed — system error, will retry
- Completed — call done, summary sent

**Signal statuses**:
- Positive — reply or call outcome suggests interest
- Neutral — engagement detected but intent unclear
- Negative — unsubscribe, reject, or clear disinterest
- Unknown — call made but outcome unclear

**Contact statuses**:
- Active — currently in a sequence
- Paused — on hold (signal or manual pause)
- Completed — finished all touchpoints
- Failed — cannot reach or invalid data
- Opted out — unsubscribed or do-not-call

Each state should have a short explanation and a clear next step when action is needed (e.g., "Paused on positive signal — ready for follow-up call?" with a button to trigger the call).

---

## 8. Accessibility and Responsiveness

The MVP must meet these UX expectations:

- Desktop-first layout optimized for 1366px+ width (typical laptop)
- Responsive behavior for tablet (768px+) and mobile browser widths (375px+)
- Keyboard access for critical actions (activate campaign, pause/resume, play recording)
- Visible focus states with 3px outline on all interactive elements
- Color not used as the only indicator of status (use icons, labels, and text also)
- Sufficient contrast (WCAG AA 4.5:1 for text, 3:1 for graphics)
- Alt text on all images and icons
- Form labels visibly associated with inputs (not just placeholder text)
- Error messages displayed inline and in summary at top of form
- Transcripts and call summaries provided as accessible text (not image-only)

---

## 9. UX Requirements

- **UX1**: The dashboard must display key email and call metrics (sent, replied, answered, signals) on first load, along with the status of active campaigns.
- **UX2**: Campaign activation must show the user the sequence assigned, script assigned, contact count, and current time before confirming activation.
- **UX3**: CSV import must separate invalid rows from valid rows with specific error reasons for each invalid row.
- **UX4**: Every email in a sequence must show the subject, body preview, and delay from the previous step before publishing.
- **UX5**: Every call in the log must show the outcome, duration, and option to play recording and read transcript without leaving the log view.
- **UX6**: The sequence monitor must display how many contacts are at each step and how many have paused signals.
- **UX7**: The operations dashboard must be understandable in under 2 minutes — show the essential metrics first, hide deep details in optional drill-down views.
- **UX8**: Recovery actions (pause sequence, pause contact, resume, trigger manual follow-up) must be visible where operators need them (campaign view, contact detail, sequence monitor).
- **UX9**: The product must work well on desktop (1366px+), tablet (768px+), and mobile browser (375px+) without requiring a separate native app.
- **UX10**: Call recordings must be playable inline with a standard HTML5 audio player; transcripts must be readable text, not static images.
- **UX11**: Every sequence must have a preview mode that shows the contact what the step 1, step 2, step 3 emails will look like.
- **UX12**: Voice script Q&A sections must be displayed in a structured format (one Q&A pair per section) so the AI assistant can reference them during calls.

---

## 10. Design Risks to Avoid

1. **A dashboard that hides campaign controls** — make pause/resume visible on the dashboard, not buried in a detail view.
2. **A sequence builder that feels like code** — use plain language (delay days, not cron or UNIX time) and show visual previews.
3. **A call log that loses context** — show contact name, campaign, and signal clearly in the list so admin knows why they're reviewing this call.
4. **A sequence monitor that shows progress without contact names** — admins need to see both aggregated progress (how many at each step) and individual contact details (which contact is paused, why).
5. **A script management screen that treats scripts like documents** — structure scripts as Q&A pairs so the AI system can parse and use them reliably.
6. **Operations dashboard that overloads with detail** — show key metrics and active campaigns first; let admins drill down for deeper charts.
7. **A responsive design that hides operational information on mobile** — operations admins use tablets and laptops in the office. Optimize for that, with graceful mobile fallback.
8. **Call recording that requires special tools** — use standard HTML5 audio player so admins can listen in any browser without plugins.

---

## 11. Implementation Notes

- The UX does not require GraphQL or advanced API patterns.
- The UX does not require a native mobile application.
- Simple HTML5 audio players are sufficient for call recordings.
- The sequence preview can be a static rendering of the email body; no need for a live email client preview.
- Script Q&A parsing can start with a simple regex pattern; advanced Markdown parsing can be added in Phase 2.
- The operations dashboard metrics can be computed nightly; real-time metrics are a Phase 2 enhancement.
- All UX screens should align with the FastAPI backend's REST API capabilities and PostgreSQL data model.

---

## 12. UX Readiness Assessment

The UX is ready for implementation if the team builds:

1. A responsive web admin experience optimized for desktop operators, with tablet and mobile support
2. A sequence-centered execution model — admins define steps, the system sends emails automatically
3. A script-based voice system — admins upload a reference script with Q&A sections, the AI assistant uses it to answer questions
4. Clear call outcome and signal visibility in the call log and sequence monitor
5. Obvious recovery and campaign controls on the dashboard and in detail views
6. Post-call email summaries sent to the team with unanswered questions and scheduling requests

That experience is fully aligned with the updated product brief and better matched to the intended users than the previous draft. The focus is on **automated execution** with **visible monitoring** and **easy recovery** — not on complex configuration or formal approval workflows.