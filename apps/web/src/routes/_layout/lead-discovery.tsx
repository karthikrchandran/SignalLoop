import { createFileRoute } from "@tanstack/react-router"

import LeadDiscoveryPage from "@/features/lead-discovery/LeadDiscoveryPage"

export const Route = createFileRoute("/_layout/lead-discovery")({
  head: () => ({
    meta: [{ title: "Lead Discovery & AI Enrichment - SignalLoop" }],
  }),
  component: LeadDiscoveryPage,
})
