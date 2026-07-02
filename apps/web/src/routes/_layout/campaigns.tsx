import { Outlet, createFileRoute, useRouterState } from "@tanstack/react-router"

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
  const pathname = useRouterState({
    select: (state) => state.location.pathname,
  })

  if (pathname !== "/campaigns") {
    return <Outlet />
  }

  return <CampaignsWorkspacePage />
}
