import { createFileRoute } from "@tanstack/react-router"

import Customer360AccountProfilePage from "@/features/customer-360/Customer360AccountProfilePage"

export const Route = createFileRoute("/_layout/customer-360/$accountId")({
  head: () => ({
    meta: [{ title: "Customer 360 Account - EngageHub" }],
  }),
  component: Customer360AccountProfileRoute,
})

function Customer360AccountProfileRoute() {
  const { accountId } = Route.useParams()

  return <Customer360AccountProfilePage accountId={accountId} />
}
