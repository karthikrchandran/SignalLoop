import { createFileRoute } from "@tanstack/react-router"

import RevenueOsHomePage from "@/features/revenue-os/RevenueOsHomePage"

export const Route = createFileRoute("/_layout/revenue-os")({
  component: RevenueOsHomePage,
  head: () => ({ meta: [{ title: "Revenue OS — ARA Global" }] }),
})
