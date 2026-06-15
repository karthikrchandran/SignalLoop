import { createFileRoute } from "@tanstack/react-router"

import VoiceAgentsPage from "@/features/voice/VoiceAgentsPage"

export const Route = createFileRoute("/_layout/voice-agents")({
  component: VoiceAgentsPage,
  head: () => ({
    meta: [{ title: "Voice Agents — SignalLoop" }],
  }),
})
