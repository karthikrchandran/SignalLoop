import {
  AlertTriangle,
  BarChart3,
  BookOpen,
  BrainCircuit,
  Briefcase,
  Building2,
  FileText,
  Home,
  Inbox,
  ListOrdered,
  Mic2,
  Plug,
  PlugZap,
  SearchCheck,
  Settings,
  Shield,
  SlidersHorizontal,
  Users,
} from "lucide-react"

import { SidebarAppearance } from "@/components/Common/Appearance"
import { Logo } from "@/components/Common/Logo"
import {
  Sidebar,
  SidebarContent,
  SidebarFooter,
  SidebarHeader,
} from "@/components/ui/sidebar"
import useAuth from "@/hooks/useAuth"
import { type Item, type ItemGroup, Main } from "./Main"
import { User } from "./User"

const baseItems: Item[] = [
  { icon: Home, title: "Dashboard", path: "/" },
  { icon: Briefcase, title: "Campaigns", path: "/campaigns" },
  { icon: BrainCircuit, title: "EngageHub AI", path: "/engagehub-ai" },
  { icon: Building2, title: "Customer 360", path: "/customer-360" },
  { icon: ListOrdered, title: "Sequences", path: "/sequences" },
  { icon: Mic2, title: "Voice Agents", path: "/voice-agents" },
  { icon: Users, title: "Contacts", path: "/contacts" },
  { icon: SearchCheck, title: "Prospecting", path: "/prospecting" },
  { icon: BarChart3, title: "Analytics", path: "/analytics" },
  { icon: FileText, title: "Templates", path: "/templates" },
  { icon: Shield, title: "Controls", path: "/controls" },
  { icon: Settings, title: "Settings", path: "/settings" },
]

const adminChatbotItems: Item[] = [
  { icon: Plug, title: "Channels", path: "/chatbot/channels" },
  { icon: BookOpen, title: "Knowledge Base", path: "/chatbot/knowledge-base" },
  { icon: Inbox, title: "Inbox", path: "/chatbot/inbox" },
  { icon: BarChart3, title: "Analytics", path: "/chatbot/analytics" },
  { icon: SlidersHorizontal, title: "Settings", path: "/chatbot/settings" },
]

const agentChatbotItems: Item[] = [
  { icon: Inbox, title: "Inbox", path: "/chatbot/inbox" },
  { icon: BarChart3, title: "Analytics", path: "/chatbot/analytics" },
]

type UserWithRole = {
  is_superuser?: boolean
  role?: string | null
}

const isChatbotAdmin = (user: UserWithRole | null | undefined) =>
  Boolean(
    user?.is_superuser ||
      user?.role === "admin" ||
      user?.role === "super_admin",
  )

export function AppSidebar() {
  const { user: currentUser } = useAuth()
  const userWithRole = currentUser as UserWithRole | null | undefined

  const items = currentUser?.is_superuser
    ? [
        ...baseItems,
        { icon: PlugZap, title: "Providers", path: "/settings/providers" },
        {
          icon: AlertTriangle,
          title: "Messaging Dead Letters",
          path: "/admin/chatbot/dead-letters",
        },
        { icon: Users, title: "Admin", path: "/admin" },
      ]
    : baseItems
  const chatbotItems = isChatbotAdmin(userWithRole)
    ? adminChatbotItems
    : agentChatbotItems
  const groups: ItemGroup[] = [
    { items },
    { title: "Messaging Hub", items: chatbotItems },
  ]

  return (
    <Sidebar
      collapsible="icon"
      role="navigation"
      aria-label="Primary"
      className="border-r border-sidebar-border"
    >
      <SidebarHeader className="px-4 py-5 group-data-[collapsible=icon]:items-center group-data-[collapsible=icon]:px-0">
        <Logo variant="responsive" tone="inverse" />
      </SidebarHeader>
      <SidebarContent className="gap-1 px-1">
        <Main groups={groups} />
      </SidebarContent>
      <SidebarFooter className="border-t border-sidebar-border/70 px-3 py-3">
        <SidebarAppearance />
        <User user={currentUser} />
      </SidebarFooter>
    </Sidebar>
  )
}

export default AppSidebar
