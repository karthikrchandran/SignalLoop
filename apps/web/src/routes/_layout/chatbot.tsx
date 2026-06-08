import { createFileRoute, Outlet, redirect } from "@tanstack/react-router"

export const Route = createFileRoute("/_layout/chatbot")({
  component: ChatbotLayout,
  beforeLoad: ({ location }) => {
    if (location.pathname === "/chatbot") {
      throw redirect({ to: "/chatbot/channels" })
    }
  },
})

function ChatbotLayout() {
  return <Outlet />
}
