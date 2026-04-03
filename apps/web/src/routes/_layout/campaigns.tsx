import { createFileRoute } from "@tanstack/react-router"

import CampaignIntakeWizardPage from "@/features/campaigns/CampaignIntakeWizardPage"

export const Route = createFileRoute("/_layout/campaigns")({
  component: CampaignsPage,
  head: () => ({
    meta: [
      {
        title: "Campaigns - EngageHub",
      },
    ],
  }),
})

function CampaignsPage() {
  return <CampaignIntakeWizardPage />
}
