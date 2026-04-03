import { createFileRoute, redirect } from "@tanstack/react-router"

export const Route = createFileRoute("/_layout/offer-packs")({
  beforeLoad: () => {
    throw redirect({ to: "/templates" })
  },
})
