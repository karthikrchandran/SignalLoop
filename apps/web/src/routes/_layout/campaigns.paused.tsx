import { createFileRoute } from "@tanstack/react-router"

import CampaignLifecycleWorkspacePage from "@/features/campaigns/CampaignLifecycleWorkspacePage"

export const Route = createFileRoute("/_layout/campaigns/paused")({
  component: CampaignsPausedRoute,
  head: () => ({
    meta: [{ title: "Paused Campaigns - SignalLoop" }],
  }),
})

function CampaignsPausedRoute() {
  return <CampaignLifecycleWorkspacePage statusFilter="paused" />
}
