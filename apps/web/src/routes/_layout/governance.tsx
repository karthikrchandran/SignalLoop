import { createFileRoute } from "@tanstack/react-router"
import GovernanceControlPage from "@/features/policies/GovernanceControlPage"

export const Route = createFileRoute("/_layout/governance")({
  component: GovernancePage,
  head: () => ({
    meta: [
      {
        title: "Governance - EngageHub",
      },
    ],
  }),
})

function GovernancePage() {
  return <GovernanceControlPage />
}
