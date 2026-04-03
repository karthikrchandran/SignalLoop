---
title: "EngageHub Design System Brief"
version: "1.1"
date: "2026-04-02"
status: "Aligned to revised MVP"
primaryAudience:
  - product_designer
  - frontend_developer
  - qa_lead
---

# EngageHub Design System Brief

## Purpose

This document gives design and frontend teams a shared MVP-ready design system brief. It supports the revised UX scope:

- responsive web admin experience
- no native mobile app requirement
- emphasis on explainability, operations visibility, and safe control

## Design Direction

EngageHub should look trustworthy, operational, and calm. The visual system should help users supervise automation, not feel overwhelmed by it.

### Core qualities

- clear
- steady
- professional
- readable under operational pressure

## Color Tokens

### Brand

- `brand.primary`: `#1D4ED8`
- `brand.primaryMuted`: `#DBEAFE`
- `brand.deep`: `#1E3A8A`

### Neutral

- `neutral.0`: `#FFFFFF`
- `neutral.50`: `#F8FAFC`
- `neutral.100`: `#F1F5F9`
- `neutral.300`: `#CBD5E1`
- `neutral.500`: `#64748B`
- `neutral.700`: `#334155`
- `neutral.900`: `#0F172A`

### Semantic

- `success`: `#10B981`
- `warning`: `#F59E0B`
- `error`: `#EF4444`
- `info`: `#3B82F6`

## Typography

- Primary font: `Inter`
- Heading weights: `600` and `700`
- Body weights: `400` and `500`
- Caption size should not drop below `12px`

Recommended scale:

- Page title: `32px`
- Section title: `24px`
- Card title: `18px`
- Body: `14px` to `16px`
- Caption: `12px`

## Spacing and Layout

- Base spacing unit: `8px`
- Card padding: `16px` to `24px`
- Section spacing: `24px` to `32px`
- Operator screens should prioritize scannability over density

### Desktop layout guidance

- left navigation
- main content area
- optional right-side context rail when it adds value

### Responsive guidance

- collapse secondary context below the primary content on smaller widths
- preserve access to timeline details and recovery actions on mobile browser widths

## Component Priorities

### Must-have MVP components

- Primary button
- Secondary button
- Status badge
- Reason code badge
- Timeline row
- Audit row
- Campaign summary card
- KPI tile
- Empty state
- Error state
- Confirmation modal
- CSV validation summary panel

### Component behavior rules

- Disabled states must be visually clear
- Error states must include a next action where possible
- Status badges must use text plus color
- Timeline entries must support concise drill-down

## Key Screen Building Blocks

### Dashboard

- KPI tiles
- queue health summary
- active campaign list
- failure and retry panel

### Campaign setup

- form sections
- content selection cards
- validation and activation summary

### Contact intake

- upload area
- mapping table
- accepted versus invalid row summary

### Lead detail

- timeline module
- reason code module
- current-state summary
- booking and handoff panel

### Handoff packet view

- lead summary
- signal summary
- objections or transcript snippets
- recommended next talking points

## Accessibility Baseline

- WCAG 2.1 AA contrast targets
- visible focus indicators
- keyboard access for all critical actions
- minimum touch target of `44px` where applicable
- status meaning must not depend on color alone

## Figma File Structure

Recommended pages:

1. Foundations
2. Components
3. Dashboard and Operations
4. Campaign Setup and Intake
5. Lead Timeline and Handoff

## Handoff Notes for Engineering

- Use design tokens consistently in code
- Keep component naming close to user intent, not framework internals
- Make reason-code and status presentation reusable across screens
- Build responsive behavior into the component library, not screen by screen

## What Changed in This Revision

The earlier design-system draft included screens and interactions for native mobile, sales-engineer feedback loops, and template-insight analytics that are not part of the MVP brief. Those are intentionally removed here so design and development stay focused on the promised first release.
