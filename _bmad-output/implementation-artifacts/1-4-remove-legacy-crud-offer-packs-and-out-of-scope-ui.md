# Story 1.4: Remove Legacy CRUD, Offer Packs, and Out-of-Scope UI

Status: ready-for-dev

## Story

As a platform engineer,
I want to remove legacy Items CRUD, offer-pack versioning, and out-of-scope UI pages,
so that the codebase contains only code relevant to the email sequence + voice calling MVP.

## Acceptance Criteria

1. **Given** apps/web/src/components/Items/ exists **When** it is deleted **Then** no Items-related components remain in the frontend
2. **Given** offer_packs routes and UI exist **When** they are removed/simplified **Then** no complex offer-pack versioning logic remains
3. **Given** out-of-scope UX pages exist (booking, handoff, ring-promotion) **When** references are removed **Then** the navigation and routing contain only MVP-relevant pages
4. **Given** dead imports exist after removal **When** they are cleaned up **Then** the application builds without warnings about missing modules

## Tasks / Subtasks

- [ ] Task 1: Delete apps/web/src/components/Items/ directory (AC: 1)
- [ ] Task 2: Remove or simplify apps/api/app/api/routes/offer_packs.py (AC: 2)
- [ ] Task 3: Delete apps/web/src/features/templates/OfferPackLibraryPage.tsx if it exists (AC: 2)
- [ ] Task 4: Remove booking, handoff, ring-promotion UI references from navigation and routing (AC: 3)
- [ ] Task 5: Clean up unused imports across frontend and backend (AC: 4)
- [ ] Task 6: Verify frontend builds cleanly (AC: 4)
- [ ] Task 7: Verify backend starts and tests pass (AC: 4)

## Dev Notes

- This is cleanup — be aggressive about removing anything not in the new UX spec
- The new navigation should only have: Dashboard, Campaigns, Contacts, Sequences, Scripts, Call Log, Sequence Monitor, Operations, Settings
### References
- [Source: ux-design-specification.md#Navigation-Model]
- [Source: epics.md#Story-1.4]

## Dev Agent Record
### Agent Model Used
### Debug Log References
### Completion Notes List
### File List
