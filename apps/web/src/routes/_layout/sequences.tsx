import { createFileRoute } from "@tanstack/react-router"

import SequencesPage from "@/features/sequences/SequencesPage"

export const Route = createFileRoute("/_layout/sequences")({
  component: SequencesPage,
  head: () => ({
    meta: [{ title: "Sequences — SignalLoop" }],
  }),
})
