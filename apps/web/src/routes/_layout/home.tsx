import { createFileRoute } from "@tanstack/react-router"

import { SuiteHomePage } from "@/features/suite/SuiteHomePage"

export const Route = createFileRoute("/_layout/home")({
  component: SuiteHomePage,
  head: () => ({ meta: [{ title: "Workspace home - SignalLoop" }] }),
})
