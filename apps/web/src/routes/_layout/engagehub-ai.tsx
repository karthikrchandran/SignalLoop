import { createFileRoute } from "@tanstack/react-router"

import EngageHubAiPage from "@/features/engagehub-ai/EngageHubAiPage"

export const Route = createFileRoute("/_layout/engagehub-ai")({
  component: EngageHubAiPage,
})
