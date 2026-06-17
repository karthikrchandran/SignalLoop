import { createFileRoute } from "@tanstack/react-router"

import ProspectingPage from "@/features/prospecting/ProspectingPage"

export const Route = createFileRoute("/_layout/prospecting")({
  head: () => ({
    meta: [{ title: "Lead Preparation - SignalLoop" }],
  }),
  component: ProspectingPage,
})
