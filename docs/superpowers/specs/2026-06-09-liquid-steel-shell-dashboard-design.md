# Liquid Steel Shell And Dashboard Design

Date: 2026-06-09
Status: approved for implementation planning

## Purpose

The current web app feels too enterprise-heavy because the shared shell, header,
dashboard, and content pages all carry similar visual weight. The product needs
a more modern workspace feel without becoming a marketing site or a novelty UI.

The approved direction is a fast operational workspace with stronger visual
hierarchy, better alignment, and page-specific spacing rules. The shell should
feel richer and more intentional, while interior pages should stop inheriting
dashboard-level compression.

## Approved Direction

Use `Liquid Steel` as the shared shell language for `apps/web`.

- Keep the product as an application workspace, not a landing-page style
  experience.
- Use a metallic dark blue sidebar and system panels.
- Keep the main content area light, readable, and scan-friendly.
- Make the dashboard the densest page type, because it is a command surface.
- Make list, detail, and setup/workbench pages less dense and more aligned than
  the dashboard.
- Replace generic card grids with clearer page zones and stronger visual
  hierarchy.

This direction should borrow the good operational structure of tools like
HubSpot without copying their flatter, busier default feel.

## Goals

- Redesign the shared shell so navigation, header, and content framing feel more
  modern and less generic.
- Redesign the dashboard so it prioritizes active work instead of blank metrics
  and quick-link cards.
- Define reusable page templates for list, detail, and setup/workbench surfaces.
- Improve alignment, spacing rhythm, and visual weight across pages.
- Reuse the existing React, Tailwind, and shadcn-style component stack instead
  of introducing a second design system.
- Keep the result mobile-safe and desktop-strong.

## Non-Goals

- Do not redesign every product page in one pass.
- Do not turn the app into a dark UI overall. The shell can be darker while the
  main work surfaces remain light.
- Do not replace routing, auth flow, or core information architecture in this
  slice.
- Do not add marketing hero sections, decorative landing content, or
  illustration-heavy filler.
- Do not introduce a brand-new component library.

## Shared Shell

The shared shell remains sidebar-based, but the current generic admin framing is
replaced with a richer workspace frame.

Sidebar:

- Keep the left navigation model from `AppSidebar`.
- Increase the visual authority of the sidebar with a metallic dark blue
  gradient.
- Use a quieter inactive state and a more obvious active state.
- Keep the sidebar persistent on desktop and sheet-based on mobile.
- Keep the item grouping model, but reduce the feeling of a long undifferentiated
  list by tuning spacing, text weight, and active contrast.

Header:

- Replace the current bare sticky bar with a real workspace header.
- The header should carry page title, short context, and primary page actions.
- The header should visually connect to the page instead of feeling like an
  isolated strip holding only the sidebar trigger.

Content frame:

- Keep a constrained content width, but use page-specific widths where needed.
- Use fewer stacked cards and more deliberate content bands.
- Preserve the current responsive structure from `routes/_layout.tsx`, but
  adjust padding, spacing, and header behavior.

## Visual System

The shell uses `Liquid Steel`:

- Primary shell color: metallic blue in the `#224e78` to `#163551` range.
- Main page background: soft blue-gray.
- Primary work surfaces: white or near-white with subtle blue border/shadow
  treatment.
- Secondary surfaces: restrained blue-on-blue fills for KPI and summary blocks.
- Accent use: primarily blue family; avoid default gray-heavy cards and avoid
  purple.

The visual system should feel premium and operational rather than playful. Blue
should carry the brand weight, while spacing and hierarchy prevent the UI from
feeling cold.

## Dashboard

The dashboard becomes a true operational landing surface rather than a generic
overview page.

Structure:

1. Top summary band
2. KPI strip
3. Main priority queue
4. Right rail for system health and recent movement
5. Secondary quick access

Top summary band:

- Page title
- Short workspace state summary
- Primary action
- Optional secondary actions like refresh or filters

KPI strip:

- Compact summary metrics
- Not all cards should look identical
- Use differentiated blue surfaces instead of repeating neutral cards

Priority queue:

- This is the dominant dashboard block
- Surface the most important active work first
- Use readable row rhythm, not decorative tiles

Right rail:

- Keep system health, alerts, and recent movement visible
- Do not let the rail overpower the priority queue

Secondary quick access:

- Move quick-link style navigation lower on the page
- Keep it supportive, not the first thing users see

## Page Templates

The dashboard should not dictate the density of every other page. The following
page types share the shell but have different interior rhythm.

### List Pages

Examples: Customer 360 accounts, campaigns, templates, contacts.

Rules:

- Stable header with title and one primary action
- One aligned filter/search row
- One dominant table or list surface
- Minimal card fragmentation
- Strong column rhythm and scan lines

List pages should feel cleaner than the dashboard. Alignment matters more than
density here.

### Detail Pages

Examples: Customer 360 account profile, channel detail, campaign detail.

Rules:

- Wider reading lanes
- Fewer simultaneous boxes
- Clear section breaks
- One dominant content column with an optional supporting rail

Detail pages should invite inspection. They must not feel like compressed
dashboards.

### Setup / Workbench Pages

Examples: provider setup, voice agent editing, advanced configuration screens.

Rules:

- Guided header and clear task framing
- Grouped controls
- Step rhythm or section rhythm where helpful
- Inline help and validation close to the edited fields

Workbench pages should feel guided and orderly, not busy.

## Alignment And Spacing Rules

The redesign must solve the alignment issue directly:

- Use consistent horizontal start lines for page title, filters, tables, and
  sections.
- Reduce unnecessary card-inside-card stacking.
- Use larger spacing jumps between major zones and tighter spacing inside zones.
- Let dense information live in rows, tables, and grouped panels instead of
  equal-weight card mosaics.
- Reserve the densest treatment for the dashboard only.

The main smell to avoid is making every page feel like a dashboard.

## Frontend Scope

The first implementation pass should focus on the shared shell and dashboard,
plus reusable layout patterns that future pages can adopt.

Primary files likely in scope:

- `apps/web/src/routes/_layout.tsx`
- `apps/web/src/components/Sidebar/AppSidebar.tsx`
- `apps/web/src/components/Sidebar/Main.tsx`
- `apps/web/src/index.css`
- `apps/web/src/routes/_layout/index.tsx`

Additional small layout helpers may be added if they reduce duplication across
page headers, KPI strips, or content sections. Avoid broad component churn.

## Rollout Boundary

Phase 1:

- Apply `Liquid Steel` to the shared shell.
- Redesign the dashboard layout and visual hierarchy.
- Introduce reusable page framing patterns for future adoption.

Phase 2:

- Apply the approved page-type rules to key pages such as Customer 360,
  Providers, Voice Agents, and Messaging Hub.

This keeps the first frontend pass focused and reviewable.

## Error And Empty States

- Empty states should use the new shell/page framing, not oversized generic
  cards.
- Section-level failures should degrade gracefully inside the page layout.
- Dashboard sections can fail independently without collapsing the whole page.
- List and detail pages should keep headers and framing stable even when data is
  missing.

## Testing And Verification

Implementation verification should include:

- `npm run build` from `apps/web`
- Targeted Playwright coverage for the dashboard shell and at least one key page
  type that adopts the new framing
- Manual viewport review for desktop and mobile
- Real-browser review of spacing, alignment, and overflow in the actual app

The visual acceptance bar is not just "build passes". The result should be
checked in the real product surface because alignment and density are part of
the requirement.

## Implementation Notes

- Preserve the existing routing and auth flow.
- Reuse the current sidebar primitives instead of replacing them wholesale.
- Use CSS variables in `index.css` for the new shell palette and supporting
  surfaces.
- Keep the dashboard vocabulary operational and product-specific, not generic
  admin-dashboard copy.
- When rolling the new shell into other pages, adapt density per page type
  rather than cloning the dashboard layout.
