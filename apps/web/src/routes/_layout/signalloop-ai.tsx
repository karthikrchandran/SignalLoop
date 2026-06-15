import { createFileRoute } from "@tanstack/react-router"

import SignalLoopAiPage from "@/features/signalloop-ai/SignalLoopAiPage"

export const Route = createFileRoute("/_layout/signalloop-ai")({
  component: SignalLoopAiPage,
})
