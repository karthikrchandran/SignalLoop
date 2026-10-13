export type WorkspaceLocation = {
  section: string
  title: string
}

const routes: Array<{ prefix: string; section: string; title: string }> = [
  { prefix: "/lead-discovery", section: "Accounts", title: "Lead Discovery" },
  { prefix: "/prospecting", section: "Accounts", title: "Lead Preparation" },
  { prefix: "/customer-360", section: "Accounts", title: "Customer 360" },
  { prefix: "/contacts", section: "Accounts", title: "Contacts" },
  { prefix: "/analytics", section: "Accounts", title: "Analytics" },
  { prefix: "/reporting", section: "Accounts", title: "Reporting" },
  { prefix: "/offer-packs", section: "Outreach", title: "Offer packs" },
  { prefix: "/campaigns", section: "Outreach", title: "Campaigns" },
  { prefix: "/signalloop-ai", section: "Outreach", title: "SignalLoop AI" },
  { prefix: "/sequences", section: "Outreach", title: "Sequences" },
  { prefix: "/voice-agents", section: "Outreach", title: "Voice Agents" },
  { prefix: "/scheduling", section: "Outreach", title: "Meetings" },
  { prefix: "/templates", section: "Outreach", title: "Templates" },
  { prefix: "/chatbot", section: "Messaging", title: "Messaging Hub" },
  { prefix: "/controls", section: "Governance", title: "Controls" },
  { prefix: "/governance", section: "Governance", title: "Governance" },
  { prefix: "/settings", section: "Governance", title: "Settings" },
  { prefix: "/platform", section: "Admin", title: "Platform" },
  { prefix: "/admin", section: "Admin", title: "Administration" },
  { prefix: "/dashboard", section: "Work", title: "Dashboard" },
  { prefix: "/revenue-os", section: "Work", title: "Revenue OS" },
  { prefix: "/home", section: "Work", title: "Home" },
]

export function resolveWorkspaceLocation(pathname: string): WorkspaceLocation {
  const match = routes.find(
    (route) => pathname === route.prefix || pathname.startsWith(`${route.prefix}/`),
  )
  if (match) return { section: match.section, title: match.title }
  if (pathname === "/") return { section: "Work", title: "Revenue OS" }
  return { section: "Workspace", title: "SignalLoop" }
}
