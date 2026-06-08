import { createFileRoute } from "@tanstack/react-router"

import ProspectingPage from "@/features/prospecting/ProspectingPage"

export const Route = createFileRoute("/_layout/prospecting")({
  head: () => ({
    meta: [{ title: "Prospecting - EngageHub" }],
  }),
  component: ProspectingPage,
})
