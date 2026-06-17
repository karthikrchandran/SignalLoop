import { createFileRoute } from "@tanstack/react-router"

import CampaignsWorkspacePage from "@/features/campaigns/CampaignsWorkspacePage"

export const Route = createFileRoute("/_layout/campaigns")({
  component: CampaignsPage,
  head: () => ({
    meta: [
      {
        title: "Campaigns - SignalLoop",
      },
    ],
  }),
})

function CampaignsPage() {
  return <CampaignsWorkspacePage />
}
