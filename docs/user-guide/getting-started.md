# SignalLoop User Guide and Getting Started

Version: July 27, 2026
Audience: SignalLoop operators, campaign managers, administrators, and new users

SignalLoop is an intelligent outreach platform for planning, launching, and monitoring multi-channel campaigns across email and voice. This guide walks you through the main screens, explains what each feature is for, and gives step-by-step instructions a new user can follow without knowing the product beforehand.

> Note: The screenshots in this guide were captured from the local development app at `http://127.0.0.1:5173`. Your environment may use a different URL, theme, sample data, or account name.

## Quick Start Checklist

Use this checklist the first time you open SignalLoop.

1. Open the SignalLoop web app.
2. Create an account or log in with your email and password.
3. Confirm you can see the left navigation menu.
4. Visit the Dashboard to monitor campaigns, ChatHub traffic, agents, and calendar handoffs.
5. Create or review templates before launching outreach.
6. Configure voice agents if you plan to use phone calls.
7. If you are an administrator, review Provider Setup before testing provider-backed workflows.
8. Prepare the lead pool from Contacts.
9. Create a campaign draft from Campaigns.
10. Select all contacts, chosen contacts, or a filtered subset from the existing lead pool.
11. Define the offer and channel strategy.
12. Review Analytics and Controls before sending at scale.
13. **ChatBot Hub:** Connect at least one messaging channel under Messaging Hub Ã¢â€ â€™ Channels, add knowledge base content, and test your bot before going live. See the [ChatBot Hub User Guide](chatbot-hub.md) for full setup instructions.

## 1. Accessing SignalLoop

### Log In

Use the Log In page when you already have an account.

![Login screen](screenshots/01-login.png)

Steps:

1. Open the SignalLoop URL in your browser.
2. If you are not already signed in, the app shows the Log In page.
3. Enter your email address in the Email field.
4. Enter your password in the Password field.
5. Select the eye icon if you need to briefly reveal or verify the password.
6. Select Log In.
7. After a successful login, SignalLoop opens the Dashboard.

Helpful notes:

- Passwords must be at least 8 characters.
- If you mistype your email or password, correct the field and try again.
- The appearance button in the top-right corner changes the visual theme.

### Create an Account

Use Sign Up if you do not yet have an SignalLoop account.

![Sign up screen](screenshots/02-sign-up.png)

Steps:

1. From the Log In screen, select Sign up.
2. Enter your full name.
3. Enter your email address.
4. Enter a password with at least 8 characters.
5. Re-enter the same password in Confirm Password.
6. Select Sign Up.
7. After signup, return to the Log In page and sign in.

Good practice:

- Use your work email address so campaigns, audit events, and permissions are tied to your organization.
- If password confirmation fails, retype both password fields carefully.

### Recover a Password

Use Password Recovery if you forgot your password.

![Password recovery screen](screenshots/03-password-recovery.png)

Steps:

1. From the Log In screen, select Forgot your password?.
2. Enter the email address for your SignalLoop account.
3. Select Continue.
4. Check your inbox for the password recovery email.
5. Open the reset link in the email.
6. Enter and confirm your new password.
7. Return to Log In and sign in with the new password.

## 2. Understanding the Main Layout

After logging in, the app uses a consistent layout.

- The left sidebar is the main navigation area.
- The top-left logo returns you to Revenue OS, the workspace landing page.
- The sidebar can be collapsed with the button in the top header.
- The Appearance control changes between light, dark, and system theme.
- The account menu at the bottom of the sidebar shows the signed-in user.
- The main workspace on the right changes based on the selected feature.

Primary navigation items:

| Menu Item | Purpose |
| --- | --- |
| Revenue OS | Landing page for the connected capture, pipeline, fulfillment, finance, and performance workspaces. |
| Dashboard | Admin command center for campaign performance, ChatHub traffic, channel health, AI-agent efficiency, and calendar handoffs. |
| Campaigns | Guided campaign intake, audience selection from the existing Contacts lead pool, filtered subsets, offer-pack assignment, and strategy setup. |
| Sequences | Build and manage multi-step outreach flows. |
| Voice Agents | Configure Alex, Morgan, and Priya voice agents, scripts, test calls, and shared knowledgebase files. |
| Contacts | Download the CSV template, analyze imports, map fields, preview rows, fix validation issues, import contacts, search the shared lead pool, and view timelines from selected contact links. |
| Customer 360 | Review one account's summary, contacts, cross-channel activity, open work, next best action, and unified timeline before follow-up. |
| Analytics | Review campaign performance, email rates, voice calls, and sequence funnel data. |
| Templates | Create reusable email templates, preview tokens, publish compliant versions. |
| Controls | Manage daily sending caps, quiet hours, and emergency pause/resume controls. |
| Settings | Update profile, password, account preferences, bot settings, and opt-out management. |
| Providers | Administrator-only setup for active email, SMS, voice, speech-to-text, text-to-speech, and LLM providers. |
| **Messaging Hub Ã¢â‚¬â€ Channels** | Connect Facebook Messenger, WhatsApp Business, and Telegram; monitor live channel health. Admin only. |
| **Messaging Hub Ã¢â‚¬â€ Knowledge Base** | Add URL, document, FAQ, and Q&A sources; monitor indexing; test bot answers before going live. Admin only. |
| **Messaging Hub Ã¢â‚¬â€ Inbox** | Triage, reply to, and resolve AI-escalated visitor conversations in real time. Admin and Agent. |
| **Messaging Hub Ã¢â‚¬â€ Analytics** | Monitor chatbot conversation volume, resolution rate, leads captured, and channel breakdowns. Admin and Agent. |

Administrators also see Providers for workspace provider setup, Admin for user management, and **Admin Ã¢â€ â€™ Messaging Dead Letters** for inspecting and retrying failed message deliveries.

## 3. Revenue OS and the Admin Command Center

Revenue OS is the landing page for the connected workspace. Select **Dashboard** in the sidebar to open SignalLoop's admin command center. The dashboard is intentionally a report surface, not a second navigation menu; use the sidebar tabs to open detailed screens.

![Dashboard screen](screenshots/04-dashboard.png)

The command center includes:

- **Campaign performance:** draft, running, and paused campaigns plus recent campaign activity.
- **ChatHub traffic:** conversation volume, containment, leads captured, escalations, opt-outs, and channel mix for the selected period.
- **Channel health:** active and ready messaging channels and any missing provider or webhook configuration.
- **AI agent operations:** contacts processed, intent signals, qualified contacts, confirmed bookings, provider errors, and booking-SLA compliance. These are efficiency measures for agents, not sales targets or incentives.
- **Calendar handoffs:** pending requests, links sent, booked meetings, cancelled requests, and the person assigned to the next step.

Steps:

1. Select **Dashboard** from the sidebar.
2. Choose a **7 days**, **30 days**, or **90 days** reporting range.
3. Review the KPI strip for the current operating picture.
4. Read each report panel for the source-specific detail.
5. Select **Refresh** after importing contacts, launching a campaign, connecting a channel, or completing a booking.
6. Use the sidebar to open the detailed workflow behind a report; the dashboard itself does not duplicate those navigation links.

Empty states are intentional. A panel that says no activity, no channels, or no handoffs means that source has not produced data for the selected period or is not configured yet; it does not represent fabricated demo metrics.

When to use it:

- At the beginning of the day to see what agents did overnight.
- Before launching outreach to confirm campaigns and channels are ready.
- During the day to catch escalations and unassigned calendar handoffs.
- At the end of a reporting period to compare agent efficiency with human sales outcomes.

## 4. Campaign Intake

Campaigns is where you create a draft campaign, choose an audience from the shared Contacts lead pool, and assign the offer/channel strategy.

![Campaign intake screen](screenshots/05-campaign-intake.png)

The Campaign intake workflow has three steps:

1. Campaign basics
2. Audience selection
3. Offer/channel strategy

Campaigns does not import CSV files or manage leads directly. Prepare and validate contacts on the Contacts page first, then return to Campaigns to select from that existing pool.

### Step 1: Campaign Basics

Steps:

1. Select Campaigns in the sidebar.
2. Enter a campaign name, such as `Q2 Product Outreach`.
3. Use a name that a teammate can understand later.
4. Select Continue.
5. SignalLoop creates a draft campaign and moves you to audience selection.

Tips for campaign names:

- Include the audience or objective, such as `Healthcare Renewal Outreach`.
- Include timing when useful, such as `May Webinar Follow-up`.
- Avoid vague names like `Test` or `New Campaign` in shared workspaces.

### Step 2: Audience Selection

Campaigns use contacts that already exist in the shared lead pool. If the list is empty or missing people, go to Contacts and import or update the lead pool before continuing.

Steps:

1. Review the available contact count at the top of Step 2.
2. Search the lead pool if you need to find a specific person, company, email, phone, or timezone.
3. Choose All contacts, Selected contacts, or Filtered subset.
4. For Selected contacts, tick the leads to include.
5. For Filtered subset, enter a subset name and rule.
6. Choose a field such as `company`, `email`, `phone`, or `timezone`.
7. Choose an operator:
   - `equals`
   - `contains`
   - `startsWith`
   - `in-list`
8. Enter the value, such as `Technology`.
9. Select Continue.
10. SignalLoop assigns the matching contacts to the campaign and moves to strategy setup.

Examples:

| Subset Goal | Field | Operator | Value |
| --- | --- | --- | --- |
| Target contacts at named companies | `company` | `in-list` | `Contoso,Fabrikam,Northwind` |
| Target a company family | `company` | `contains` | `Health` |
| Target local calling windows | `timezone` | `equals` | `America/New_York` |
| Target known phone contacts | `phone` | `startsWith` | `+1` |

### Step 3: Offer and Channel Strategy

Strategy controls which offer pack and channel behavior apply to the campaign.

Steps:

1. Choose a published offer pack version if one is available.
2. If you do not want to assign an offer pack, leave the field blank.
3. Review the Channel strategy JSON.
4. For an email-only campaign, use a simple strategy such as `{"channel":"email"}`.
5. For more advanced scenarios, define the channel structure your team supports.
6. Select Save strategy.
7. Confirm the success message appears.

Important:

- Only published and compliant template or offer-pack versions should be used for live campaigns.
- Ask an administrator or campaign owner before changing a shared strategy.
- Keep JSON valid. Missing quotes, commas, or braces can prevent the strategy from saving.

## 5. Sequences

Sequences are reusable multi-step outreach flows that combine emails, waits, and voice steps.

![Sequences screen](screenshots/06-sequences.png)

What you can do here:

- Review existing sequences.
- See whether a sequence is Active, Draft, or Paused.
- Understand each sequence step in order.
- Create a new draft sequence.
- Delete draft or unwanted sequences.

### Create a New Sequence

Steps:

1. Select Sequences in the sidebar.
2. Select New Sequence.
3. Enter a name, such as `Spring Promotion Series`.
4. Enter a short description.
5. Select Create.
6. The new sequence appears as a Draft.
7. Select Edit when you are ready to adjust the sequence details.

Sequence building tips:

- Start with one immediate email.
- Add waits between messages so contacts are not overwhelmed.
- Use a voice step only when a human-like follow-up is appropriate.
- Pause a sequence when content, compliance, or audience quality needs review.

### Read a Sequence Card

Each sequence card shows:

- Name and description.
- Status badge.
- Number of contacts enrolled, when available.
- Ordered steps, such as email, wait, and voice.
- Edit and delete actions.

## 6. Voice Agents

Voice Agents lets you choose, configure, and test AI voice outreach behavior.

![Voice agents screen](screenshots/07-voice-agents.png)

SignalLoop includes three voice agents with English and Hindi preview/script starter support:

| Agent | Best For | Tone |
| --- | --- | --- |
| Alex | B2B outreach, appointment confirmations, executive communication | Professional and authoritative |
| Morgan | Re-engagement, follow-ups, support check-ins, relationship-driven outreach | Empathetic and conversational |
| Priya | Hindi-aware re-engagement, customer check-ins, relationship-led follow-ups | Friendly and reassuring |

### Choose an Agent

Steps:

1. Select Voice Agents in the sidebar.
2. Review the Alex, Morgan, and Priya cards.
3. Choose English or Hindi from Voice language.
4. Select the agent you want to configure.
5. Use Preview to hear a sample greeting.
6. Select Stop if you want to stop playback.

### Configure a Call Script

Steps:

1. Open the Script tab.
2. Choose a Call Objective:
   - Appointment Reminder
   - Follow-up Call
   - Re-engagement
   - Product Introduction
   - Feedback / Survey
   - Custom
3. Review the script text.
4. Edit the script to match your campaign.
5. Use personalization tokens such as `{{contact.firstName}}`, `{{company.name}}`, or `{{campaign.topic}}`.
6. Select Preview Test Call to initiate a preview test call flow.

Script writing tips:

- Keep the opening sentence short and clear.
- Mention who the agent represents.
- Ask one question at a time.
- Avoid jargon contacts will not recognize.
- Include a polite fallback if now is not a good time.

### Add Shared Knowledgebase Files

Knowledgebase files give Alex, Morgan, and Priya additional context when contacts ask questions outside the script.

![Voice knowledgebase screen](screenshots/07b-voice-knowledgebase.png)

Steps:

1. Open the Knowledgebase tab.
2. Click the upload area.
3. Choose one or more PDF, DOCX, or TXT files.
4. Review the uploaded file list.
5. Remove any wrong file with the remove icon.
6. Select Save Knowledgebase.
7. Confirm the saved message appears.

Good files to upload:

- Product FAQ.
- Pricing overview.
- Appointment policies.
- Support escalation rules.
- Campaign-specific offer details.

Avoid uploading:

- Outdated policy documents.
- Internal-only confidential notes not approved for agent use.
- Files with conflicting instructions.

### Review Call Settings

The Call Settings tab describes advanced configuration for retry count, call windows, voicemail behavior, consent recording, and Do Not Call integration. These options depend on telephony provider setup.

## 7. Templates

Templates are reusable outreach messages. They support tokens so the same template can personalize content for each contact.

![Templates screen](screenshots/08-templates.png)

What you can do here:

- Start from prebuilt starter templates.
- Create custom email drafts.
- Preview token rendering.
- Publish selected templates after guardrail validation.
- Review published templates.

### Use a Starter Template

Steps:

1. Select Templates in the sidebar.
2. Review the Starter Templates section.
3. Choose a template that matches your use case, such as Welcome, Promotional, Re-engagement, Reminder, or Thank You.
4. Select Use Template.
5. The editor fields are prefilled.
6. Review and edit the subject and body.

### Create a Template Draft

Steps:

1. Enter a Template name.
2. Set Channel, usually `email`.
3. Enter the Subject.
4. Enter Body content.
5. Use tokens for personalization, such as:
   - `{{contact.firstName}}`
   - `{{contact.company}}`
   - `{{offer.expiryDate}}`
   - `{{sender.name}}`
6. Select Save draft.
7. Confirm the feedback message appears.

Writing tips:

- Put the most important message in the first paragraph.
- Use a clear call to action.
- Keep the subject specific and honest.
- Provide default token values where possible.

### Preview Tokens

Steps:

1. In Publish Readiness, choose a template from the dropdown.
2. Select Preview tokens.
3. Review the rendered preview.
4. Check for unresolved tokens.
5. If unresolved tokens appear, edit the template or token configuration.

### Publish a Template

Steps:

1. Select a draft template.
2. Preview tokens first.
3. Select Publish selected.
4. Wait for guardrail validation.
5. Confirm the template appears under Published Templates.

Important:

- Published templates are the safest versions to use in campaigns.
- Guardrail-compliant templates reduce the risk of invalid personalization or policy violations.

## 8. Analytics

Analytics helps you understand performance across campaigns, email sequences, and voice outreach.

![Analytics screen](screenshots/09-analytics.png)

What you can do here:

- Change the reporting period.
- Review summary performance cards.
- Review past campaign runs.
- Compare email and voice performance.
- Inspect the sequence funnel.

### Change the Reporting Period

Steps:

1. Select Analytics in the sidebar.
2. Open the period dropdown in the top-right.
3. Choose Last 7 days, Last 30 days, Last 90 days, or Year to date.
4. Review updated metrics.

### Read Summary Cards

The top cards show:

- Total Emails Sent.
- Average Open Rate.
- Average Click-through Rate.
- Voice Calls Completed.

Each card includes a change indicator compared with the previous period.

### Review Past Campaign Runs

Steps:

1. Scroll to Past Campaign Runs.
2. Review campaign name, channel, assigned voice agent, sent count, open rate, click-through rate, date, and status.
3. Look for outliers, such as unusually low open rates or paused campaigns.
4. Use results to decide whether to adjust templates, segmentation, or send timing.

### Read the Sequence Funnel

The Email Sequence Funnel shows how many contacts reached each step.

Use it to answer questions like:

- How many contacts enrolled?
- Where did the largest drop-off occur?
- How many contacts converted?
- Should we revise the offer, timing, or final nudge?

## 9. Outreach Controls

Controls protects your sender reputation and gives administrators emergency stop/start capability.

![Controls screen](screenshots/10-controls.png)

### Review Daily Sending Limits

Steps:

1. Select Controls in the sidebar.
2. Review the displayed daily sending limit state.
3. Use emergency pause if the current limits are not safe for the moment.

Guidance:

- Use conservative limits when warming a sender domain.
- Increase limits gradually as engagement and deliverability remain healthy.
- Use lower campaign-level caps for experimental campaigns.
- In the current app, daily-limit editing is not available on this page.

### Review Do Not Disturb Hours

Steps:

1. Review the displayed quiet-hours state.
2. If outreach needs to stop immediately, use Emergency controls.

How quiet hours work:

- No emails or calls go out during the configured window.
- Scheduled campaigns wait until sending resumes.
- This protects recipients from late-night or inappropriate outreach.
- In the current app, quiet-hour editing is not available on this page.

### Pause or Resume All Outreach

Emergency controls stop or restart outreach across every campaign and sequence.

![Emergency controls screen](screenshots/10b-controls-emergency.png)

Steps to pause:

1. Scroll to Emergency controls.
2. Enter a reason, such as `Compliance review` or `System maintenance`.
3. Select Pause all outreach.
4. Confirm the paused banner or feedback message appears.
5. Notify campaign owners that sending has stopped.

Steps to resume:

1. Return to Emergency controls.
2. Confirm the reason for the pause has been resolved.
3. Select Resume outreach.
4. Confirm the feedback message appears.
5. Monitor campaigns and analytics after resuming.

Use emergency pause when:

- A compliance issue is being investigated.
- A template mistake was discovered after launch.
- Provider errors are affecting sending.
- The wrong contacts or subset were assigned.
- Your organization needs an immediate temporary hold.

## 10. Contacts and Timeline

Contacts is the shared lead pool for SignalLoop. Add leads here before creating campaigns so the same contacts can be reused across outreach efforts.

![Contacts screen](screenshots/11-contacts.png)

When no contact is selected, the page shows import, mapping, search, and lead list controls.

What you can do here:

- Download the CSV template.
- Analyze a CSV before saving it.
- Map incoming columns to SignalLoop fields.
- Preview valid rows.
- Review row-level validation issues.
- Import valid contacts into the shared lead pool.
- Search and refresh the lead table.
- Confirm email, name, company, phone, and timezone values before campaign selection.

### Import Leads

Steps:

1. Select Contacts in the sidebar.
2. Select CSV template if you need the expected columns.
3. Choose a `.csv` file.
4. Select Analyze.
5. Review the analysis summary, including total rows, valid rows, and invalid rows.
6. Map source columns to SignalLoop fields such as `email`, `firstName`, `lastName`, `company`, `phone`, and `timezone`.
7. Review the Preview panel for valid rows.
8. Review the Validation panel for row-level issues.
9. Select Import contacts when email is mapped and validation is acceptable.
10. Confirm the feedback message and lead pool table update.

Recommended CSV fields:

| Field | Why It Matters |
| --- | --- |
| `email` | Required for email outreach and deduplication. |
| `firstName` | Used for personalization tokens. |
| `lastName` | Helps sales and support teams identify contacts. |
| `company` | Used in templates, scripts, and filtered campaign subsets. |
| `phone` | Required for voice outreach. |
| `timezone` | Helps schedule sends and calls at appropriate local times. |

### Search Leads

Steps:

1. Enter an email, name, company, or phone value in Search leads.
2. Select Refresh or press Enter.
3. Review matching leads in the Lead pool table.
4. Clear or change the search text and refresh again to return to the wider pool.

When a contact is selected, the timeline can show:

- State transitions.
- Emails sent.
- Email opens.
- Call sessions.
- Signals.
- Booking events.
- Routing events.

### View a Contact Timeline

Steps:

1. From the Lead pool table, select a contact row (or select the contact name link).
2. The right-hand panel switches to the contact's timeline view.
3. Review the contact's identity card at the top: name, email, company, phone, and timezone.
4. Scroll the timeline to see chronological events, newest first by default.
5. Use the event-type filter (when available) to narrow to a specific stream, such as Emails sent or Call sessions.
6. Select an event entry to expand details such as subject line, template version, call duration, or routing decision.
7. Use the Back or Close action in the panel header to return to the lead pool view.

Reading the timeline:

| Event Type | What It Means |
| --- | --- |
| State transition | The contact moved between progression states (for example, Enrolled Ã¢â€ â€™ Contacted Ã¢â€ â€™ Engaged). |
| Email sent | An outbound email was dispatched. The entry records template, subject, and send time. |
| Email open | A tracked open was recorded for a previously sent email. |
| Call session | A voice call was attempted or completed. The entry records the agent, duration, and outcome. |
| Signal | A behavioural signal such as a click, reply, or unsubscribe was captured. |
| Booking event | A meeting or appointment was scheduled or updated. |
| Routing event | The contact was rerouted between sequences, owners, or workspaces. |

When to use the timeline:

- Before a manual follow-up call, to see what the contact has already received.
- During QA, to confirm a campaign step was actually delivered.
- During investigation, when a contact reports unexpected outreach or wants to opt out.
- During analytics review, to verify a funnel drop-off is reflected at the individual level.

## Customer 360

Customer 360 is the account-level workspace for a company. It shows the account summary, contacts, chatbot activity, email sequence activity, voice call activity, prospecting research, open work, next best action, and unified account timeline.

Use Customer 360 before follow-up when you need to understand what has happened across every channel for one account.


## 11. Settings

Settings lets each user manage their own account.

![Settings profile screen](screenshots/11-settings-profile.png)

Available tabs:

- My profile
- Password
- Danger zone

### Edit Profile Information

Steps:

1. Select Settings in the sidebar.
2. Open My profile.
3. Review your full name and email.
4. Select Edit.
5. Update your full name or email.
6. Select Save.
7. Confirm the success message appears.

Notes:

- Use a recognizable full name so audit logs and user lists are easy for teammates to understand.
- Changing an email may affect future login behavior.

### Change Password

![Settings password screen](screenshots/12-settings-password.png)

Steps:

1. Select Settings in the sidebar.
2. Open the Password tab.
3. Enter your current password.
4. Enter your new password.
5. Confirm the new password.
6. Select Update Password.
7. Confirm the success message appears.
8. Use the new password next time you log in.

Password rules:

- Password must be at least 8 characters.
- New Password and Confirm Password must match.

### Delete Account

The Danger zone tab contains account deletion controls.

Steps:

1. Select Settings.
2. Open Danger zone.
3. Read the warning carefully.
4. Start the delete confirmation only if you are certain.
5. Confirm account deletion when prompted.

Warning:

- Account deletion is permanent.
- Do not delete an account that owns active campaigns without first transferring responsibility or confirming with an administrator.


## 12. Admin User Management

Some users may see Providers and Admin menu items. Both are available only to superusers.

Admins can typically:

- Select workspace providers for email, LLM, and STT from Providers.
- View users.
- Add users.
- Manage permissions.
- Review whether a listed user is the current user.

Basic steps:

1. Select Admin in the sidebar.
2. Review the users table.
3. Select Add User to create a new account.
4. Enter required user details.
5. Save the user.
6. Confirm the user appears in the table.

If you do not see Providers or Admin, your account does not have superuser permissions.


## 13. Sign Out

Sign out when you are done for the day, when switching accounts, or when working on a shared computer.

Steps:

1. Open the account menu at the bottom of the sidebar.
2. Select Sign out.
3. The app returns to the Log In page.

## 14. Messaging Hub — ChatBot Hub

ChatBot Hub is the AI-powered messaging section built into SignalLoop. It lets you connect Facebook Messenger, WhatsApp Business, and Telegram to a shared bot that answers visitor questions using your own knowledge base, captures leads, escalates complex conversations to your team, and gives you a real-time inbox to manage those handoffs.

There is no separate portal. ChatBot Hub lives inside the same SignalLoop sidebar you already use.

---

### Quick Start for New Admins

1. Log in to SignalLoop.
2. Select **Channels** under Messaging Hub in the sidebar.
3. Connect at least one channel (Facebook Messenger or WhatsApp Business recommended for MVP).
4. Select **Knowledge Base** and add at least one URL, document, or FAQ source.
5. Select **Index Now** and wait for the status to turn **Ready**.
6. Open the **Test Bot** sheet and ask the bot a question about your business.
7. When the answer looks correct, your bot is ready for live traffic.
8. Optionally configure bot behavior under **Settings â†’ Bot Settings**.
9. Monitor live conversations in **Inbox**.

---

### 1. ChatBot Hub Navigation

After logging in, expand the **Messaging Hub** group in the left sidebar.

| Sidebar item | Who can see it | Purpose |
|---|---|---|
| Channels | Admin only | Connect and manage Facebook Messenger, WhatsApp Business, Telegram |
| Knowledge Base | Admin only | Add content sources, monitor indexing, test bot answers |
| Inbox | Admin and Agent | Triage escalated conversations, reply, resolve |
| Analytics | Admin and Agent | Monitor chatbot performance and channel trends |
| Settings â†’ Bot Settings | Admin only | Configure AI disclosure, lead capture, business hours, retention |
| Settings â†’ Opt-outs | Admin only | Review and re-enable opted-out visitors |

The Inbox badge shows a count of open escalations. The badge clears when all escalated threads are resolved.

---

### 2. Channels

Channels is where you connect each messaging provider and check live connection health.

#### Channel Status Cards

The page shows one card per supported channel:

| Status label | Color | Meaning |
|---|---|---|
| Disconnected | Grey | Not yet set up |
| Connecting | Yellow | Webhook verification in progress |
| Connected Â· Active | Green | Live and accepting messages |
| Inactive | Grey | Credentials saved but channel toggled off |
| Error | Red | Provider API error; hover for detail |
| Pending Approval | Blue | Provider-side review required (e.g., Meta WhatsApp) |

#### Connect a Channel

Steps:

1. Select **Channels** in the sidebar.
2. Find the card for the channel you want to connect.
3. Select **Connect**.
4. The connection sheet opens.

##### Facebook Messenger

1. Enter your **Page ID** (visible in your Facebook Page settings under About).
2. Enter your **Page Access Token** (generated from Meta for Developers under your app's Messenger product).
3. Enter a **Webhook Verify Token** â€” any secret string you choose; you will paste this into the Meta dashboard webhook setup.
4. Select **Save & Verify**.
5. Go to your Meta for Developers dashboard, open your app's Messenger Webhooks, and paste the same Verify Token plus your SignalLoop callback URL.
6. Once Meta sends a successful challenge, the card turns **Connected Â· Active**.

##### WhatsApp Business

1. Enter your **Phone Number ID** (from Meta for Developers, WhatsApp â†’ Phone Numbers).
2. Enter your **WhatsApp Business Account ID** (WABA ID from Meta Business Manager).
3. Enter your **Access Token** (System User or temporary token from Meta for Developers).
4. Enter a **Webhook Verify Token** â€” any secret string you choose.
5. Select **Save & Verify**.
6. Set up the webhook in Meta for Developers â†’ WhatsApp â†’ Configuration, using the SignalLoop callback URL and your Verify Token.
7. The card turns **Connected Â· Active** after verification.

**Important â€” WhatsApp 24-hour window:** WhatsApp platform rules allow businesses to reply only within 24 hours of the visitor's last message. When this window has expired, the reply composer in Inbox is automatically disabled and shows a compliance banner. This is a platform requirement, not a configurable setting.

##### Telegram

1. Create a Telegram bot via [@BotFather](https://t.me/BotFather) if you do not yet have one (send `/newbot` and follow the steps).
2. Copy the **Bot Token** BotFather provides.
3. Enter the Bot Token in the connection sheet.
4. Enter a **Webhook Secret** â€” any secret string; SignalLoop will use it to verify incoming Telegram requests.
5. Select **Save & Verify**.
6. SignalLoop registers the webhook with Telegram automatically.
7. The card turns **Connected Â· Active**.

#### Toggle a Channel On or Off

Steps:

1. On the Channels page, select **Edit** on the connected channel card.
2. Toggle the **Active** switch off to temporarily pause the channel without losing credentials.
3. Toggle back on to resume.

Visitors who message while the channel is inactive will not receive a bot reply. Their messages are not lost â€” they appear in Inbox as unprocessed.

#### Delete a Channel

Steps:

1. Select **Edit** on the channel card.
2. Select **Delete connection**.
3. Confirm the deletion.
4. Credentials are permanently removed. You must reconnect and re-verify if you change your mind.

---

### 3. Knowledge Base

The Knowledge Base is the content your bot uses to answer visitor questions. You can add websites, documents, and manually written FAQ text.

#### Source Types

| Type | What it indexes |
|---|---|
| Website URL | Crawls the URL and linked pages up to depth 5, up to 50 pages per source |
| Document | Uploads PDF, DOCX, or TXT files up to 20 MB each |
| FAQ / Free-form text | Paste or type content directly |
| Q&A pairs | Structured question-and-answer pairs for precise bot responses |

#### Add a URL Source

Steps:

1. Select **Knowledge Base** in the sidebar.
2. Open the **Website URLs** tab.
3. Enter one or more URLs, separated by commas or new lines.
4. Set **Crawl depth** (1â€“5, default 2). Depth 1 indexes only the page you enter; depth 2 also follows links from that page.
5. Select **Add Source**.
6. The source row appears with status **Pending**.
7. Select **Index Now** (or wait for the next scheduled run) to start indexing.

#### Upload a Document

Steps:

1. Open the **Documents** tab.
2. Select **Upload document**.
3. Choose a PDF, DOCX, or TXT file under 20 MB.
4. Select **Add Source**.
5. The document appears with status **Pending**.
6. Select **Index Now** to start processing.

#### Add FAQ or Q&A Content

Steps:

1. Open the **FAQ / Q&A** tab.
2. Enter questions and answers directly into the text area, or use the structured Q&A entry form.
3. Select **Save**.
4. Select **Index Now** to make the content available to the bot.

#### Understanding Indexing Status

| Status | Meaning |
|---|---|
| Pending | Waiting to be indexed |
| Indexing | Background job is crawling or parsing the source |
| Ready | Content is indexed and the bot will use it |
| Failed | Error occurred; expand the row to see the failure reason |
| Stale | Re-index is recommended because the source was recently updated |

The **Indexing progress banner** appears below the page header while a job is running. It disappears automatically when all sources reach Ready or Failed.

#### Re-index Your Knowledge Base

Re-indexing updates the bot's understanding when your content changes.

Manual re-index:

1. Select **Re-index All** at the top of the Knowledge Base page.
2. A background job starts. The progress banner appears.
3. Wait for all sources to return to **Ready**.

Scheduled re-index:

- By default, SignalLoop re-indexes every workspace at **02:00 local time** nightly.
- Change the schedule time in **Settings â†’ Bot Settings â†’ Re-index Schedule**.

In-flight bot conversations continue using the previous index version until they end. New conversations pick up the updated index automatically.

#### Test Your Bot

The Test Bot sheet lets you check answers before going live.

Steps:

1. Select **Test Bot** at the top of the Knowledge Base page.
2. Enter a question in the input field.
3. Select **Ask**.
4. Review:
   - The bot's answer
   - The **AI disclosure** label (visible on every response)
   - The **source name** and **chunk excerpt** that grounded the answer
   - The **similarity score** (higher means more relevant; 0.4 and above is the escalation threshold)
5. If the answer is wrong or the confidence is low, add or improve the relevant source content and re-index.

Use Test Bot to build confidence before connecting a live channel. The goal is: the bot answers your 10 most common visitor questions accurately before any real visitor uses it.

---

### 4. Bot Runtime Behavior

Understanding how the bot works helps you configure it well.

#### How the Bot Responds

When a visitor sends a message:

1. The bot checks whether the visitor has opted out. If yes, no response is sent.
2. The bot retrieves the most relevant chunks from your knowledge base.
3. The bot constructs a prompt using your knowledge, conversation history, and visitor message.
4. The LLM generates a grounded answer.
5. Every response includes your configured **AI disclosure** text.
6. The response is delivered to the visitor on the originating channel within 5 seconds (p95).

#### Escalation

The bot escalates to your Inbox when:

- The visitor explicitly asks for a human (e.g., "Can I speak to someone?").
- The bot's confidence falls below the threshold (default: 0.4 cosine similarity).
- Three consecutive turns produce low-confidence responses.

On escalation, the bot sends your configured escalation message to the visitor and the thread appears in **Inbox** in real time.

**Out of hours:** If escalation happens outside your configured business hours, the bot sends your out-of-hours message and tags the thread accordingly. Your team handles it the next business day.

#### Non-text Messages

When a visitor sends an image, voice note, document, sticker, or location, the bot sends a graceful fallback message (configurable in Settings). No knowledge base query is performed for non-text content.

#### Bot-Off Mode

You can turn off the bot for a specific channel in the channel's edit sheet. All inbound messages go directly to Inbox for manual response, with no bot engagement.

---

### 5. Inbox

Inbox is where your team handles escalated conversations and human handoffs.

#### Thread List

Steps:

1. Select **Inbox** in the sidebar.
2. The left panel shows a list of threads sorted by last activity.
3. Each thread row shows:
   - Channel icon (Messenger, WhatsApp, Telegram)
   - Visitor name or channel ID
   - Message preview
   - Last activity time
   - Status badge

#### Thread Status Badges

| Status | Meaning |
|---|---|
| Bot active | Bot is handling the conversation |
| Escalated | Bot triggered handoff; waiting for agent |
| Agent active | An agent has replied and owns this thread |
| Resolved | Thread marked complete by an agent |
| Out of hours | Escalated outside configured business hours |
| Opted out | Visitor has sent STOP; bot is permanently blocked |

#### Filter Threads

Steps:

1. Use the filter bar above the thread list.
2. Filter by **Channel** (Facebook, WhatsApp, Telegram), **Status**, or **Date range**.
3. The list updates without a full page reload.

#### View a Thread

Steps:

1. Select a thread row.
2. The right panel shows the full message history.
3. Messages are labeled: **Bot**, **Visitor**, or **Agent**.
4. Bot messages show the AI disclosure label.

#### Reply to a Visitor

Steps:

1. Open a thread.
2. Type your reply in the **Reply composer** at the bottom.
3. Select **Send**.
4. The reply is delivered to the visitor on their channel and optimistically appended to the thread view.
5. Thread status changes to **Agent active**.

**WhatsApp only:** If the visitor's last message is more than 24 hours old, the reply composer is replaced with a non-dismissable compliance banner: *"WhatsApp 24-hour reply window has expired. You cannot send a new message until the visitor contacts you again."* This is a WhatsApp platform rule.

**Opted-out threads:** The reply composer is disabled for opted-out visitors. The opt-out notice is shown in the thread header. To re-enable, go to **Settings â†’ Opt-outs**.

#### Resolve and Reopen a Thread

Steps to resolve:

1. Open the thread.
2. Select **Resolve** in the thread header.
3. The thread moves to **Resolved** status and drops out of the default open filter.

Steps to reopen:

1. Filter threads to include **Resolved** status.
2. Open the resolved thread.
3. Select **Reopen**.
4. The thread returns to **Escalated** or **Agent active**.

#### Real-time Updates

New escalations appear at the top of the thread list automatically without refreshing the page. A toast notification appears when a new escalation arrives. The Inbox badge in the sidebar updates in real time.

If your browser loses the real-time connection, the inbox falls back to polling automatically.

#### Export Conversations (Admin only)

Steps:

1. Open the action menu in a thread's header, or use the Inbox bulk-action toolbar.
2. Select **Export**.
3. Choose **CSV** or **JSON**.
4. Choose a **date range** and optionally filter by **channel**.
5. Large exports run as a background job and download when ready.

Export includes: message timestamps, sender role, text, bot confidence score, and captured lead details.

---

### 6. Lead Capture

When a visitor expresses interest in purchasing, requesting a demo, or asking about pricing, the bot can collect contact details and create or update a SignalLoop contact automatically.

#### How Lead Capture Works

1. The bot detects purchase intent keywords or the conversation reaches the configured turn threshold.
2. The bot presents your **privacy notice** and requests consent.
3. If the visitor consents, the bot collects name and email or phone.
4. A contact is created or updated in SignalLoop with:
   - Source channel
   - Tag: `chatbot-lead`
   - Captured intent
5. If the visitor declines, the conversation continues normally. The bot does not re-prompt during the same session.

#### Configure Lead Capture

Steps:

1. Select **Settings â†’ Bot Settings** in the sidebar.
2. Open the **Lead Capture** section.
3. Toggle **Enable lead capture** on or off.
4. Edit the **Intent keywords** that trigger the flow.
5. Edit the **Privacy notice** text shown to visitors before PII collection.
6. Enter your **Privacy policy URL**.
7. Select **Save**.

**Privacy and consent requirement:** Lead capture never collects a visitor's name, email, or phone before showing the privacy notice and receiving explicit consent. This is enforced by the system and cannot be bypassed. Consent accept and decline events are recorded in the audit log.

---

### 7. Bot Settings

Bot Settings controls all configurable bot behavior in one place.

Steps:

1. Select **Settings** in the sidebar.
2. Select the **Bot Settings** tab (or go to **Chatbot â†’ Settings** if your workspace shows it as a separate link).

#### AI and Disclosure

| Setting | Purpose | Default |
|---|---|---|
| Bot persona description | Up to 300 chars injected into the LLM system prompt. Describes who the bot is. | "I am a helpful assistant for [workspace name]." |
| AI disclosure text | Appended to or included in every bot message. Cannot be left blank. | "I'm an AI assistant." |
| Configured LLM | The language model used for responses | Groq Llama 3.1 8B |

**AI disclosure is mandatory.** Clearing the field and saving returns a validation error. This protects your visitors and satisfies channel platform policies.

#### Lead Capture

See section 6 above for field-by-field guidance.

#### Business Hours

| Setting | Purpose |
|---|---|
| Timezone | The workspace timezone used to evaluate business hours |
| Business days | Which days of the week are active |
| Business hours | Start and end time for each active day |
| Out-of-hours message | Sent to the visitor when escalation occurs outside business hours |

When a visitor messages outside business hours and the bot cannot answer:

- The escalation message is sent.
- The thread is tagged **Out of hours** in Inbox.
- Your team can reply the next business day.

#### Compliance

| Setting | Min | Default | Purpose |
|---|---|---|---|
| Conversation retention | 30 days | 90 days | How long conversation data is kept before automatic purge |
| Token cap per session | 1 | 4000 | Maximum LLM tokens consumed per visitor session before graceful escalation |

**Retention purge:** Every night the system automatically deletes or anonymises conversation records older than the configured retention period. Aggregated analytics are preserved. Purged conversations no longer appear in Inbox, Analytics, or exports.

#### Re-index Schedule

Set the time (workspace local) when the nightly knowledge base re-index runs. Default is 02:00.

---

### 8. Opt-outs

When a visitor sends a **STOP**, **Unsubscribe**, **Cancel**, or **Quit** message on any channel, the system:

1. Immediately blocks all further bot responses to that visitor.
2. Creates an opt-out record visible to admins.
3. Keeps the visitor's thread visible in Inbox with an **Opted out** badge.

#### View Opt-outs

Steps:

1. Select **Settings** in the sidebar.
2. Open the **Opt-outs** tab.
3. The table lists: channel, visitor identifier, opted-out time, and the actor who recorded the opt-out (system-detected or manual).

#### Re-enable a Visitor (Admin only)

Use this only when a visitor has explicitly re-consented outside the system (for example, by emailing your team and asking to re-subscribe).

Steps:

1. Find the visitor row in the Opt-outs table.
2. Select **Re-enable**.
3. A confirmation dialog asks you to confirm the explicit re-consent basis.
4. Select **Confirm**.
5. The opt-out record is removed and the visitor can receive bot responses again.
6. The re-enable action is recorded in the audit log.

**Never re-enable without genuine visitor re-consent.** Messaging an opted-out contact can violate WhatsApp, Messenger, and applicable data-protection regulations.

---

### 9. Analytics

Analytics lets administrators and agents monitor chatbot performance over time.

Steps:

1. Select **Analytics** under Messaging Hub in the sidebar.
2. Choose a date range from the picker at the top right.
3. The page refreshes data automatically.

#### Summary Cards

| Card | What it shows |
|---|---|
| Total conversations | Number of unique visitor sessions in the period |
| Bot resolved | Conversations fully handled by the bot without escalation |
| Escalations | Conversations handed off to a human agent |
| Leads captured | Consented contact records created or updated from chatbot sessions |

#### Charts

- **Conversation volume over time** â€” daily or weekly trend line of total conversations.
- **Outcome breakdown by channel** â€” bar chart showing bot-resolved vs escalated vs opted-out per channel.
- **Resolution rate** â€” percentage of conversations resolved by the bot without escalation. Target: above 70% for a well-tuned knowledge base.

#### Outcome Table

The outcome table breaks down each channel by volume, escalation rate, opt-out count, and lead capture count. Use it to identify which channel or knowledge gap is generating the most escalations.

#### Refreshed indicator

A small badge on the page shows when the data was last aggregated (updated every 15 minutes). Analytics data is pre-aggregated and does not scan raw conversation records at query time.

---

### 10. Compliance at a Glance

| Requirement | How SignalLoop enforces it |
|---|---|
| AI disclosure | Every bot message includes the configured disclosure text. Cannot be disabled. |
| Opt-out enforcement | STOP keyword immediately halts bot responses on any channel. Re-enable requires explicit admin action and audit logging. |
| WhatsApp 24-hour window | Reply composer locks once the window expires. Enforced in the UI and the delivery adapter. |
| Privacy consent before PII | Lead capture never collects name/email/phone before the privacy notice and consent step. |
| Non-text fallback | Images, voice notes, documents, stickers, and locations receive a configurable graceful fallback without knowledge base queries. |
| Data retention | Conversation records are automatically purged after the configured retention period (minimum 30 days). |
| Workspace isolation | Every knowledge source, conversation, opt-out record, analytics snapshot, and channel is scoped to your workspace. Other workspaces cannot see your data. |
| Webhook signature verification | All incoming channel webhooks are verified using provider-issued signatures before payload processing. Unsigned payloads are rejected with HTTP 401. |

---

### Glossary

| Term | Meaning |
|---|---|
| Bot-active | A conversation currently being handled by the AI bot |
| Escalated | A conversation the bot has handed off to a human agent |
| Knowledge source | A URL, document, or FAQ entry that the bot uses to answer questions |
| Indexing | The background process that reads a knowledge source and stores it in the vector database |
| Chunk | A small segment of a knowledge source (300â€“500 tokens) stored for retrieval |
| Similarity score | A number between 0 and 1 indicating how relevant a retrieved chunk is to the visitor's question. 0.4 is the escalation threshold. |
| AI disclosure | A required label in every bot message that tells visitors they are talking to an AI |
| Lead capture | The process of collecting a visitor's contact details with consent and creating a SignalLoop contact |
| Opt-out | A visitor who has sent STOP and cannot receive further bot messages |
| WhatsApp window | The 24-hour period after a visitor's last WhatsApp message during which a reply can be sent |
| Dead letter | A message that failed processing after 3 retries; visible to operators under Admin â†’ Messaging Dead Letters |
| Retention | How long conversation records are kept before automatic purge (minimum 30 days) |

## 15. Recommended First Campaign Workflow

Follow this end-to-end workflow when launching your first campaign.

1. Prepare templates.
   - Go to Templates.
   - Use a starter template or create a draft.
   - Preview tokens.
   - Publish the selected template.
2. Prepare voice behavior if calls are included.
   - Go to Voice Agents.
   - Select Alex, Morgan, or Priya.
   - Review the call script.
   - Upload relevant knowledgebase files.
   - Run a preview test call if available.
3. Confirm provider setup if you are an administrator.
   - Go to Providers.
   - Confirm local or managed providers are selected for Email, SMS, Voice, STT, TTS, and LLM.
4. Configure safety controls.
   - Go to Controls.
   - Review daily sending limits and quiet hours.
   - Use emergency pause/resume if an operational hold is needed.
5. Prepare contacts.
   - Go to Contacts.
   - Download the CSV template if needed.
   - Analyze the lead CSV.
   - Map email, name, company, phone, and timezone fields.
   - Review preview rows and validation issues.
   - Import the contacts into the shared lead pool.
6. Create the campaign.
   - Go to Campaigns.
   - Enter a clear campaign name.
   - Choose all contacts, selected contacts, or a filtered subset from the existing lead pool.
   - Save the channel strategy.
7. Monitor performance.
   - Go to Analytics.
   - Review campaign run metrics.
   - Watch open rate, click-through rate, completed calls, and funnel conversion.
8. Investigate contacts when needed.
   - Open contact timelines from available drilldown links.
   - Filter events by type or date.
   - Review reason codes and transcripts where available.
9. Pause if something looks wrong.
   - Go to Controls.
   - Enter a pause reason.
   - Select Pause all outreach.

## 16. Troubleshooting

### I cannot log in

Try this:

1. Confirm you are using the correct email address.
2. Re-enter your password.
3. Use Forgot your password? if needed.
4. Ask an administrator to confirm your account exists.

### The Campaign Continue button is disabled

Common causes:

- Step 1 requires a campaign name longer than 2 characters.
- Step 2 requires at least one available contact for All contacts.
- Step 2 requires at least one picked contact for Selected contacts.
- Step 2 requires a filter value for Filtered subset.
- Step 3 requires valid channel strategy text.

If no contacts are available, go to Contacts, import or refresh the lead pool, and then return to Campaigns.

### My contact CSV has invalid rows

Try this:

1. Check required fields like email.
2. Remove blank rows.
3. Confirm column headers are present.
4. Check for invalid email addresses.
5. Analyze the corrected file again from Contacts.

### Token preview shows unresolved tokens

Try this:

1. Confirm the token name is spelled correctly.
2. Confirm the token exists in the sample payload or contact data.
3. Add a default value where supported.
4. Preview again before publishing.

### Voice demo does not play

Try this:

1. Confirm browser audio is not muted.
2. Wait a moment for speech voices to load.
3. Try a different browser if local speech synthesis is unavailable.
4. Select Demo again.

### Outreach needs to stop immediately

Use Controls:

1. Open Controls.
2. Scroll to Emergency controls.
3. Enter a reason.
4. Select Pause all outreach.
5. Confirm sending is paused.

## 17. Glossary

| Term | Meaning |
| --- | --- |
| Campaign | A named outreach effort with an audience, offer, and channel strategy. |
| Sequence | A reusable multi-step flow combining emails, waits, and voice steps. |
| Template | A reusable email message with personalization tokens. |
| Token | A placeholder such as `{{contact.firstName}}` that is replaced at send time. |
| Segment | A subset of the audience selected by rules. |
| Offer pack | A published, versioned bundle of offer content used by a campaign. |
| Channel strategy | Configuration that defines whether outreach uses email, voice, or another supported channel pattern. |
| Lead pool | The shared list of contacts available for selection by any campaign. |
| Voice agent | An AI voice persona (Alex, Morgan, or Priya) that places outbound calls. |
| Knowledgebase | Files supplied to voice agents for context beyond the script. |
| Quiet hours | A configured window where no outreach is sent. |
| Emergency pause | An administrator action that immediately halts all outreach. |
| Workspace | The tenant boundary that scopes campaigns, contacts, and audit events. |
| Contact timeline | A chronological record of events for one contact. |
| Guardrail validation | A safety check before publishing templates or outreach assets. |
| ChatBot Hub | The AI-powered messaging section in SignalLoop. Handles visitor Q&A, lead capture, and human handoffs via Facebook Messenger, WhatsApp Business, and Telegram. |
| Knowledge source | A URL, document, or FAQ entry that the chatbot uses to answer visitor questions. |
| Indexing | The background process that reads a knowledge source and stores it for vector retrieval. |
| Escalation | A chatbot conversation transferred to a human agent because the bot could not answer confidently. |
| AI disclosure | A required label in every bot message that tells visitors they are talking to an AI. |
| Lead capture | The process of collecting a visitor's contact details with consent and creating a SignalLoop contact. |
| Opt-out | A visitor who sent STOP and cannot receive further bot messages until an admin re-enables them. |
| WhatsApp window | The 24-hour period after a visitor's last WhatsApp message during which a reply can be sent. |
| Dead letter | A message that failed processing after 3 retries; visible to operators under Admin â†’ Messaging Dead Letters. |
| Retention | How long conversation records are kept before automatic purge (minimum 30 days). |

## 18. Print and Share

This guide is the single comprehensive reference for all SignalLoop features, including ChatBot Hub.

- `getting-started.md` â€” editable Markdown source.
- `getting-started.html` â€” browser-viewable version for sharing and printing.

When printing from the HTML version:

1. Open `getting-started.html` in a browser.
2. Press `Ctrl+P`.
3. Choose Save as PDF or a physical printer.
4. Enable background graphics if your browser offers that option.
5. Print or save.
