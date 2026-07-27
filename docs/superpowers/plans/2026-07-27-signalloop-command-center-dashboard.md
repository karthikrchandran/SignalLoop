# SignalLoop admin command center dashboard

## Outcome

Replace the text-heavy SignalLoop dashboard with an admin command center. The existing sidebar remains the only navigation surface; the dashboard itself is a read-only operational view of campaigns, ChatHub traffic, channel health, AI-agent activity, and calendar handoffs.

## Implementation

1. Add a dashboard page that loads campaign, ChatHub, channel, scheduling, and KPI data independently.
2. Add a 7/30/90-day range selector and refresh action.
3. Show KPI cards for active campaigns, contacts processed, conversations, leads, meetings, and escalations.
4. Add report panels for campaign performance, ChatHub traffic, channel health, AI-agent operations, and scheduling/calendar handoffs.
5. Use explicit empty and unavailable states instead of fabricated metrics or navigation cards.
6. Route `/dashboard` to the new page and keep `/` as the Revenue OS landing page.
7. Verify with the web build and a browser smoke check against the running SignalLoop app.

## Acceptance criteria

- No quick-access/navigation cards or links are rendered in the dashboard body.
- Existing sidebar tabs remain unchanged.
- Real API data is used when available; each source can fail without taking down the rest of the page.
- Empty workspaces clearly say that no activity/configuration exists for the selected period.
- Scheduling data visibly distinguishes pending handoffs, sent links, booked meetings, and assigned people.
- The page remains useful with zero real data so production data can be loaded later.
