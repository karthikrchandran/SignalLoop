import { createFileRoute } from "@tanstack/react-router"

import CampaignLifecycleWorkspacePage from "@/features/campaigns/CampaignLifecycleWorkspacePage"

export const Route = createFileRoute("/_layout/campaigns/running")({
  component: CampaignsRunningRoute,
  head: () => ({
    meta: [{ title: "Running Campaigns - SignalLoop" }],
  }),
})

function CampaignsRunningRoute() {
  return <CampaignLifecycleWorkspacePage statusFilter="active" />
}
