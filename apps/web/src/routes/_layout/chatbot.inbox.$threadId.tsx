import { createFileRoute } from "@tanstack/react-router"

import { InboxPage } from "@/features/chatbot"

export const Route = createFileRoute("/_layout/chatbot/inbox/$threadId")({
  component: ThreadDetailRoute,
  head: () => ({
    meta: [{ title: "Chatbot Thread - SignalLoop" }],
  }),
})

function ThreadDetailRoute() {
  const { threadId } = Route.useParams()
  return <InboxPage threadId={threadId} />
}
