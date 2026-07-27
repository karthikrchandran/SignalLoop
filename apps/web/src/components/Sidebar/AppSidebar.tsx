import { useMemo, useState } from "react"
import {
  AlertTriangle,
  BarChart3,
  BookOpen,
  BrainCircuit,
  Briefcase,
  Building2,
  CalendarClock,
  Cog,
  FileText,
  Home,
  Inbox,
  ListOrdered,
  MessageSquare,
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
import { cn } from "@/lib/utils"
import type { LucideIcon } from "lucide-react"
import { type Item, type ItemGroup, Main } from "./Main"
import { User } from "./User"

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

const baseItems: Item[] = [
  { icon: Home, title: "Revenue OS", path: "/" },
  { icon: Home, title: "Dashboard", path: "/dashboard" },
  { icon: Briefcase, title: "Campaigns", path: "/campaigns" },
  { icon: BrainCircuit, title: "SignalLoop AI", path: "/signalloop-ai" },
  { icon: Building2, title: "Customer 360", path: "/customer-360" },
  { icon: ListOrdered, title: "Sequences", path: "/sequences" },
  { icon: Mic2, title: "Voice Agents", path: "/voice-agents" },
  { icon: CalendarClock, title: "Meetings", path: "/scheduling" },
  { icon: Users, title: "Contacts", path: "/contacts" },
  { icon: SearchCheck, title: "Lead Preparation", path: "/prospecting" },
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

type SectionId = "outreach" | "messaging" | "admin"

const adminItems: Item[] = [
  { icon: PlugZap, title: "Providers", path: "/settings/providers" },
  {
    icon: AlertTriangle,
    title: "Dead Letters",
    path: "/admin/chatbot/dead-letters",
  },
  { icon: Users, title: "Admin", path: "/admin" },
]

export function AppSidebar() {
  const { user: currentUser } = useAuth()
  const userWithRole = currentUser as UserWithRole | null | undefined
  const [activeSection, setActiveSection] = useState<SectionId>("outreach")

  const chatbotItems = isChatbotAdmin(userWithRole)
    ? adminChatbotItems
    : agentChatbotItems

  type SectionDef = {
    id: SectionId
    label: string
    icon: LucideIcon
    group: ItemGroup
  }

  const sections = useMemo<SectionDef[]>(() => {
    const base: SectionDef[] = [
      {
        id: "outreach",
        label: "Outreach",
        icon: Briefcase,
        group: { items: baseItems },
      },
      {
        id: "messaging",
        label: "Messaging",
        icon: MessageSquare,
        group: { title: "Messaging Hub", items: chatbotItems },
      },
    ]
    if (currentUser?.is_superuser) {
      base.push({
        id: "admin",
        label: "Admin",
        icon: Cog,
        group: { title: "Admin", items: adminItems },
      })
    }
    return base
  }, [chatbotItems, currentUser?.is_superuser])

  const activeGroup =
    sections.find((s) => s.id === activeSection)?.group ??
    sections[0].group

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
      <SidebarContent className="gap-0 px-1">
        {/* Section switcher — icons at rest, label slides in on hover/active */}
        <div className="flex items-center gap-0.5 px-2 pb-1 pt-1 group-data-[collapsible=icon]:flex-col group-data-[collapsible=icon]:items-center group-data-[collapsible=icon]:px-0">
          {sections.map((section) => {
            const Icon = section.icon
            const isActive = activeSection === section.id
            return (
              <button
                key={section.id}
                type="button"
                onClick={() => setActiveSection(section.id)}
                title={section.label}
                className={cn(
                  "group/btn flex items-center overflow-hidden rounded-md px-2 py-1.5 text-xs font-medium transition-all duration-200",
                  "group-data-[collapsible=icon]:justify-center group-data-[collapsible=icon]:px-2 group-data-[collapsible=icon]:py-2",
                  isActive
                    ? "bg-white/16 text-white gap-1.5"
                    : "gap-0 text-sidebar-foreground/55 hover:bg-white/10 hover:text-white hover:gap-1.5",
                )}
              >
                <Icon className="size-3.5 shrink-0 group-data-[collapsible=icon]:size-4" />
                <span
                  className={cn(
                    "whitespace-nowrap overflow-hidden transition-all duration-200",
                    "group-data-[collapsible=icon]:hidden",
                    isActive
                      ? "max-w-[5rem]"
                      : "max-w-0 group-hover/btn:max-w-[5rem]",
                  )}
                >
                  {section.label}
                </span>
              </button>
            )
          })}
        </div>
        <Main groups={[activeGroup]} />
      </SidebarContent>
      <SidebarFooter className="border-t border-sidebar-border/70 px-3 py-3">
        <SidebarAppearance />
        <User user={currentUser} />
      </SidebarFooter>
    </Sidebar>
  )
}

export default AppSidebar
