import { createFileRoute, Outlet, useRouterState } from "@tanstack/react-router"

import Customer360AccountsPage from "@/features/customer-360/Customer360AccountsPage"

export const Route = createFileRoute("/_layout/customer-360")({
  head: () => ({
    meta: [{ title: "Customer 360 - EngageHub" }],
  }),
  component: Customer360Route,
})

function Customer360Route() {
  const pathname = useRouterState({
    select: (state) => state.location.pathname,
  })

  if (pathname !== "/customer-360") {
    return <Outlet />
  }

  return <Customer360AccountsPage />
}
