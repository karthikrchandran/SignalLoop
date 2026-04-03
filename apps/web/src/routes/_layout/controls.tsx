import { createFileRoute } from "@tanstack/react-router"

import GovernanceControlPage from "@/features/policies/GovernanceControlPage"

export const Route = createFileRoute("/_layout/controls")({
  component: GovernanceControlPage,
})
