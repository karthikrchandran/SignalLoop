import { createFileRoute } from "@tanstack/react-router"

import CampaignLifecycleWorkspacePage from "@/features/campaigns/CampaignLifecycleWorkspacePage"

export const Route = createFileRoute("/_layout/campaigns/draft")({
  component: CampaignsDraftRoute,
  head: () => ({
    meta: [{ title: "Draft Campaigns - SignalLoop" }],
  }),
})

function CampaignsDraftRoute() {
  return <CampaignLifecycleWorkspacePage statusFilter="draft" showBuilder />
}
