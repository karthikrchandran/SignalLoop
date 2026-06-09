import { createFileRoute } from "@tanstack/react-router"

import Customer360AccountsPage from "@/features/customer-360/Customer360AccountsPage"

export const Route = createFileRoute("/_layout/customer-360")({
  head: () => ({
    meta: [{ title: "Customer 360 - EngageHub" }],
  }),
  component: Customer360AccountsPage,
})
