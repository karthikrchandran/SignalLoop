# Bootstrap, Funding, Pricing, and Exit Strategy

## Purpose

This document is the business operating guide for launching the Agentic Revenue Workforce while bootstrapped. It covers cost, paid pilots, pricing, fundraising, differentiation, launch milestones, and acquisition readiness.

It is a planning model, not legal, tax, accounting, securities, or investment advice. Validate financing instruments and customer contracts with qualified advisers in the company's jurisdiction.

## Recommendation

Stay bootstrapped through three to five paid design-partner pilots. Charge implementation and usage separately. Raise an angel or pre-seed round only after proving that one repeatable lead-to-cash workflow produces customer value and renewals.

Do not wait for every provider integration before speaking with customers. Sell an honestly scoped pilot using working product surfaces and simulators, then configure only the integrations required by that pilot.

## Monthly cost model

Use four cost stages. Do not apply the managed-production budget to a private
demo or a scheduled launch partner.

Code-generation LLM usage on the founder's development laptop is excluded from
this operating model. LLM usage inside the customer workflow, including
proposal, email, and summary drafting, is included.

### Private development and demonstration

This stage uses the development laptop, local PostgreSQL or a separate free
database project, local Redis, Mailpit, Ollama, and provider simulators. It
does not send live customer communications.

| Expense | Monthly planning range |
|---|---:|
| Local application infrastructure | $0 |
| Local database, Redis, and storage | $0 |
| Local LLM and transcription API usage | $0 |
| Incremental electricity | $0-$3 |
| Domain and miscellaneous tools | $0-$2 |
| **Expected total** | **$0-$5** |

### Scheduled pre-revenue launch partner

Use a separate desktop for customer operation during an agreed four-to-six-hour
window. Keep development and testing on the laptop. The recommended stack is:

- Built web application, FastAPI, and required workers on the desktop.
- Neon Free PostgreSQL as the system of record.
- Local Redis for ephemeral coordination.
- Local Ollama with Qwen3 8B, or Qwen3 4B on smaller hardware.
- Cloudflare Tunnel for scheduled public access.
- Customer-owned SMTP or low-volume Amazon SES.
- Local faster-whisper only for batch transcription when required.
- Human approval for proposal, email, pricing, discount, and financial actions.

| Expense | Monthly planning range |
|---|---:|
| Web, API, and workers on existing desktop | $0 |
| Neon Free PostgreSQL | $0 |
| Local Redis, Ollama, and optional transcription | $0 |
| Cloudflare Tunnel | $0 |
| Customer SMTP or low-volume SES | $0-$2 |
| Incremental electricity | $2-$8 |
| Domain and miscellaneous tools | $0-$5 |
| **Expected total** | **$2-$15** |

The operating guide is
[`docs/operations/scheduled-launch-desktop.md`](../../operations/scheduled-launch-desktop.md).

Neon and Supabase are both managed PostgreSQL services. Neon is preferred here
because SignalLoop already supplies its own application, API, authentication,
and provider layer. Supabase is a reasonable later choice only if its Auth,
Storage, or Realtime capabilities will be adopted deliberately.

As of July 2026, [Neon Free](https://neon.com/pricing) includes 100 compute-unit
hours and 0.5 GB storage per project, with scale-to-zero when inactive. Treat
the free tier as a launch allowance, not a permanent production entitlement.

Upgrade before reaching 400 MB storage or 75 compute-unit hours, when a customer
requires 24/7 operation, when multiple customers depend on the desktop, or when
the first meaningful recurring payment can fund managed infrastructure.

### Managed bootstrap production

| Expense | Monthly planning range |
|---|---:|
| Web hosting | $20-$50 |
| API and background workers | $50-$150 |
| PostgreSQL | $15-$75 |
| Redis, file storage, and backups | $10-$50 |
| Monitoring and logging | $0-$60 |
| Transactional email | $15-$30 |
| LLM development usage | $25-$150 |
| Domains and miscellaneous tools | $25-$75 |
| **Expected total** | **$160-$640** |

This is the managed-production budget, not the immediate pre-revenue budget. It
excludes founder compensation, contractors, legal work, customer
data/enrichment, and live campaign volume.

### Three paid pilots

Assumptions:

- Three customers.
- Approximately 500 voice minutes per customer monthly.
- Moderate text-agent usage.
- Customer-owned outbound domains and provider credentials where practical.

| Expense | Monthly planning range |
|---|---:|
| Core infrastructure | $250-$600 |
| LLM execution | $75-$300 |
| Voice stack | $180-$450 |
| Email and SMS | $50-$200 |
| Logs, recordings, and storage | $30-$100 |
| **Expected total before enrichment and labor** | **$585-$1,650** |

### Ten small customers

For ten customers averaging 500 voice minutes monthly, plan for approximately $1,700-$7,000 monthly before labor. The large range reflects call duration, model choice, enrichment, retained recordings, support, and channel mix.

### Current external cost anchors

- [Vercel Pro](https://vercel.com/docs/plans/pro-plan) lists a $20 monthly platform fee with included usage credit.
- [Neon](https://neon.com/pricing) describes approximately $15 monthly as a typical intermittent 1 GB Launch workload.
- Neon Free currently includes 100 compute-unit hours and 0.5 GB storage per project; inactive compute scales to zero.
- [Supabase Free](https://supabase.com/pricing) currently includes a 500 MB database but can pause after one week of inactivity and does not include automatic backups.
- [Amazon SES](https://aws.amazon.com/ses/pricing/) lists $0.10 per 1,000 outbound emails and an introductory free allowance for eligible message charges.
- [OpenAI models](https://developers.openai.com/api/docs/models) publish token rates for cost-sensitive, balanced, and frontier models.
- [Vapi](https://vapi.ai/pricing) lists a $0.05 per-minute hosting cost before model-provider costs.
- [Twilio US Voice](https://www.twilio.com/en-us/voice/pricing/us) lists US outbound local calling separately from the voice-agent platform.
- [Twilio SendGrid](https://www.twilio.com/en-us/products/email-api/pricing) publishes current transactional email plans.

Use these as budget anchors only. Record real blended cost after every pilot and revise the model monthly.

## Cost-control rules

- Keep development and customer operation on separate machines and separate databases.
- Run the launch desktop and public tunnel only during the agreed operating window.
- Use a built frontend and non-reloading API process; do not expose development servers to the customer.
- Prefer Neon Free over local production PostgreSQL for the pre-revenue launch, while keeping local Redis and Ollama on the desktop.
- Use Qwen3 locally for proposal and email prose; keep price, quantity, tax, margin, and discount calculations deterministic.
- Require human approval for every externally sent or financially material action.
- Do not start voice or post-call workers unless the customer workflow requires them.
- Do not self-host an internet-facing SMTP server.
- Give every tenant, agent, campaign, provider, and day a spend limit.
- Route routine classification and drafting to a cost-efficient model; reserve frontier reasoning for high-value exceptions.
- Cache stable instructions and retrieve only relevant customer context.
- Store structured summaries instead of replaying entire histories.
- Stop loops on reply, opt-out, completion, disqualification, budget, manager pause, or repeated failure.
- Require customer-owned sending domains, inboxes, phone numbers, and high-volume provider accounts where practical.
- Pass through voice, SMS, enrichment, and unusual model usage.
- Never advertise unlimited communications.
- Keep software and AI cost below 20% of recurring subscription revenue.

### Pre-revenue upgrade gates

Remain on the scheduled desktop only while:

- The customer accepts scheduled availability.
- Neon storage remains below 400 MB.
- Neon compute remains below 75 compute-unit hours monthly.
- Manual start, stop, support, and backup work remains manageable.
- A temporary outage would not create material customer harm.

Upgrade to managed hosting and a paid database tier when:

- The first meaningful recurring payment is received.
- More than one customer depends on the environment.
- Unattended or 24/7 operation is required.
- Database free-tier limits or backup requirements are approaching.
- The workflow handles material financial, regulated, or high-risk data.

## Customer acquisition plan

### Target market

Begin with one of:

- Custom manufacturers.
- Agencies.
- Professional-services firms.

The first customers should create proposals before delivering and invoicing. They should have enough transaction volume to measure time saved but not require a year-long enterprise procurement cycle.

### Paid design-partner offer

Sell a 90-day pilot:

> We will automate one measurable revenue workflow, integrate the systems required for that workflow, and report the economic result.

Recommended pilot loop:

```text
lead
  -> qualification
  -> controlled follow-up
  -> meeting
  -> proposal draft and approval
  -> invoice or payment-follow-up workflow
```

Pilot requirements:

- Paid setup deposit.
- Named executive sponsor and operational owner.
- Baseline metrics before activation.
- Weekly review.
- Customer-owned credentials or explicit usage allowance.
- Access to outcome data.
- Permission to produce an anonymized or named case study if agreed results are reached.
- Written description of what is live, simulated, configured during onboarding, and excluded.

### What may be sold before live integration

It is acceptable to sell an integration-dependent pilot before production configuration when:

- The product workflow works with a simulator.
- The adapter contract and implementation path exist.
- The customer knows the integration is an onboarding deliverable.
- The contract contains the dependency, acceptance test, and fallback.
- No marketing material describes the integration as live before verification.

### Proof required

Measure:

- Speed to first response.
- Qualified-lead and meeting rate.
- Proposal turnaround and acceptance.
- Follow-up SLA compliance.
- Payment collection improvement.
- Human hours saved.
- Agent correction and escalation rate.
- Cost per successful outcome.
- Revenue influenced.
- Pilot-to-paid conversion and renewal.

## Pricing strategy

Charge for a business outcome and operating capability, not only human seats.

### Price components

1. Platform subscription.
2. Implementation and onboarding.
3. Included agent/activity allowance.
4. Metered communications, enrichment, storage, and overages.

### Initial price card

| Offering | Suggested price |
|---|---:|
| 90-day design-partner pilot | $2,500-$5,000 setup plus $1,500/month |
| Starter | $750-$1,000/month |
| Growth Revenue Team | $2,000-$3,500/month |
| Quote-to-Cash Revenue OS | $4,000-$7,500/month |
| Enterprise/custom | From $10,000/month |
| Additional usage | Metered or paid through customer-owned providers |

### Packaging

**Starter**

- One autonomous agent.
- One funnel.
- ChatHub or text outreach.
- Basic manager dashboard.
- Limited included usage.

**Growth Revenue Team**

- Three agents.
- ChatHub, eCRM, lead scoring, funnels, sequences, and pipeline follow-up.
- Manager approvals, run history, and efficiency reporting.

**Quote-to-Cash Revenue OS**

- Proposal, order, invoice, collection, and operations agents.
- Commercial and financial approval controls.
- Reconciliation and management reporting.
- Higher workflow and data allowances.

### Pricing rules

- Charge implementation while onboarding remains service-heavy.
- Offer 10%-15% annual savings.
- Avoid large lifetime discounts.
- Avoid success-only pricing until attribution is contractually precise.
- A pilot may include a modest outcome bonus against an agreed metric.
- Review gross margin and support hours by customer every month.
- Increase price before adding complex customer-specific integrations.

The entry price for a standalone AI BDR can be much lower; for example, [Artisan announced](https://www.artisan.co/blog/artisan-launches-ava-2.0-the-first-autonomous-ai-bdr-now-self-serve) self-service pricing starting at $250 monthly. Revenue OS should justify a higher price through quote-to-cash depth, control, and measurable operational value.

## Fundraising strategy

### Preferred sequence

1. Bootstrap the working demo and Phase 1 product.
2. Obtain three to five paid pilots.
3. Convert at least two to annual subscriptions.
4. Publish one measured case study.
5. Raise angels/pre-seed only to accelerate a proven vertical playbook.
6. Approach institutional VC after retention and repeatable onboarding exist.

### Angel/pre-seed target

Planning range:

- Raise $400,000-$750,000.
- Fund 15-18 months of focused runway.
- Target approximately 10%-15% cumulative pre-seed dilution.
- Use a standard, counsel-reviewed instrument appropriate to the company jurisdiction.

[Y Combinator](https://www.ycombinator.com/documents) publishes post-money SAFE documents for eligible jurisdictions. The valuation cap must reflect actual traction and dilution, not a headline from another AI company.

[Carta's recent benchmark](https://carta.com/data/linkedin-vc-fundraising-benchmarks-2026/) reported a $24.3 million median seed valuation and $4.1 million median capital raised in its dataset. That is a market reference, not an appropriate automatic valuation for a product without repeatable revenue.

### Suggested use of a $500,000 round

| Use | Allocation |
|---|---:|
| Engineering and agent reliability | $225,000 |
| Integrations and customer onboarding | $90,000 |
| Founder-led sales and marketing | $70,000 |
| Security, legal, and compliance | $55,000 |
| Infrastructure and AI usage | $35,000 |
| Contingency | $25,000 |

### What to ask from investors

Ask for more than capital:

- Introductions to target customers.
- Experience with B2B SaaS, AI agents, CRM, ERP, or vertical software.
- Help recruiting one strong product/agent engineer and customer-success lead.
- Security, enterprise-sales, and pricing guidance.
- Follow-on capacity or strong relationships with later-stage investors.
- A clean, founder-aligned process without unnecessary control terms.

### Institutional VC gate

Consider a $1.5-$3 million institutional round after demonstrating:

- 10-20 paying customers.
- $20,000-$50,000 MRR.
- Repeatable pilot-to-paid conversion.
- Strong retention and customer references.
- A vertical onboarding playbook that does not rely entirely on founder knowledge.
- Measurable gross margin and provider cost.
- Low customer concentration.
- Evidence that quote-to-cash depth drives adoption or retention.

## Competitive differentiation

### Do not compete with Zoho horizontally

Zoho has broad distribution, many business applications, prebuilt agents, custom-agent tooling, and digital employees. Revenue OS should not claim differentiation merely because it also has AI agents.

### Own the quote-to-cash vertical

The differentiated workflow is:

```text
engagement
  -> qualification
  -> proposal
  -> margin
  -> production or service delivery
  -> invoice
  -> collection
  -> incentive and management reporting
```

### Positioning pillars

- Agents continue after the meeting.
- Human and digital workers share one customer history.
- AI-agent efficiency is measured separately from human incentives and targets.
- Commercial and financial actions are approval-controlled and auditable.
- Customers can choose model, channel, CRM, and ERP providers.
- Vertical templates reach value faster than a generic agent builder.
- Revenue attribution extends from signal to collected cash.

### Initial positioning

Category:

> Agentic Revenue Workforce for quote-to-cash businesses.

Headline:

> From first conversation to paid invoice, your human and AI revenue team works in one system.

Proof statement:

> AI agents that do not stop after booking the meeting.

### Initial vertical templates

- Agency Revenue Team.
- Custom Manufacturing Revenue Team.
- Professional Services Revenue Team.

## What must be built before fundraising

- [ ] Digital-worker identities in eCRM.
- [ ] Agent runtime, triggers, tools, policies, approvals, and budgets.
- [ ] AgentOps manager control tower.
- [ ] ChatHub inbound qualification and handoff.
- [ ] Lead scoring, funnels, rules, and sequencing.
- [ ] Proposal Agent with deterministic margin and tax validation.
- [ ] Invoice and Payment Follow-up Agents.
- [ ] Complete run history and tool-call audit.
- [ ] Agent cost, quality, and outcome dashboard.
- [ ] Local provider simulators.
- [ ] Email/calendar plus the accounting integration required by the first pilot.
- [ ] Three vertical demo workspaces.
- [ ] Security baseline, tenant isolation, backup, and recovery proof.

Do not delay fundraising proof to build:

- A public agent marketplace.
- Ten ERP connectors.
- Full video demonstrations.
- A broad social/content suite.
- Customer-specific SAP mappings without a design partner.

## Exit strategy

Do not operate the company only for an exit. Build a profitable business that creates strategic options.

### Potential acquirer categories

- CRM and customer platforms: Salesforce, HubSpot, Zoho, Microsoft, Freshworks.
- Revenue platforms: Salesloft, Outreach, ZoomInfo.
- Communications: Twilio, Zoom.
- Finance and ERP: Intuit, SAP, Oracle, Sage, Xero.
- Vertical-software groups and private-equity portfolio companies.

### Why a buyer may care

- Quote-to-cash agent technology.
- Vertical workflow templates.
- Customer and outcome distribution.
- Proprietary conversion, proposal, production, payment, and agent-efficiency data.
- A trusted agent control plane with audit and approvals.
- Integrations that expand the buyer's platform.
- Strong retention and expansion in an attractive vertical.

Code without customers, retention, data, or distribution is unlikely to create a strong acquisition outcome.

### Evidence of strategic demand

- [Salesloft acquired Drift](https://www.salesloft.com/company/newsroom/salesloft-acquires-drift) to combine conversational engagement with revenue orchestration.
- [HubSpot acquired Clearbit](https://ir.hubspot.com/news-releases/news-release-details/hubspot-completes-acquisition-b2b-intelligence-leader-clearbit) to bring B2B intelligence into its customer platform.
- [ServiceNow acquired Logik.ai](https://newsroom.servicenow.com/press-releases/details/2025/ServiceNow-to-boost-CRM-offering-with-acquisition-of-Logik-ais-best-in-class-AI-powered-CPQ-solution/default.aspx) for AI-powered CPQ capability.
- [Salesforce agreed to acquire Fin](https://www.salesforce.com/uk/news/press-releases/2026/06/15/salesforce-signs-definitive-agreement-to-acquire-fin/) for proven agent technology and an established customer base.

These transactions show strategic interest; they are not valuation comparisons.

### Acquisition readiness checklist

- [ ] Clean founder, employee, and contractor IP assignments.
- [ ] Clean cap table and board/consent records.
- [ ] Standard customer contracts and data-processing terms.
- [ ] Tenant isolation, access control, audit export, and incident process.
- [ ] Documented architecture, migrations, tests, and recovery procedure.
- [ ] Portable provider interfaces without hidden credential dependencies.
- [ ] Low customer concentration.
- [ ] Retention, expansion, and cohort reporting.
- [ ] Traceable revenue attribution.
- [ ] Clearly licensed data and enrichment sources.
- [ ] No unsupported claims about autonomous or live-provider capability.

## Immediate 90-day operating plan

### Days 1-30

- Complete the Phase 1 digital-worker and AgentOps foundation.
- Prepare the separate scheduled launch desktop using `docs/operations/scheduled-launch-desktop.md`.
- Create separate development and launch database projects.
- Configure Neon Free, local Redis, local Ollama, and Cloudflare Tunnel.
- Rehearse start, stop, health-check, backup, and isolated restore procedures.
- Prepare three vertical demo workspaces.
- Create the pilot contract, security summary, ROI baseline, and pricing sheet.
- Recruit 20 qualified design-partner prospects.
- Conduct discovery against one repeatable workflow.

### Days 31-60

- Close the first paid pilot.
- Configure only the required providers.
- Measure baseline and agent performance weekly.
- Complete Proposal Agent review flow.
- Publish founder-led content explaining quote-to-cash agents.

### Days 61-90

- Close pilots two and three.
- Convert the first successful pilot to an annual contract.
- Produce one measured case study.
- Update unit economics from actual provider bills.
- Decide whether customer revenue can fund the next six months.
- Raise angels only if additional capital clearly accelerates proven demand.
