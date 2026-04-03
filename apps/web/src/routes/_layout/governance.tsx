import { createFileRoute, redirect } from "@tanstack/react-router"

export const Route = createFileRoute("/_layout/governance")({
  beforeLoad: () => {
    throw redirect({ to: "/controls" })
  },
})
