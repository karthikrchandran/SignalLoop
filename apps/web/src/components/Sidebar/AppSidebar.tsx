import { useQuery } from "@tanstack/react-query"
import { useRouterState } from "@tanstack/react-router"
import type { LucideIcon } from "lucide-react"
import {
  AlertTriangle,
  BarChart3,
  BookOpen,
  BrainCircuit,
  Briefcase,
  Building2,
  CalendarClock,
  Compass,
  FileText,
  Home,
  Inbox,
  LayoutDashboard,
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
import { useEffect, useMemo, useState } from "react"
import { SidebarAppearance } from "@/components/Common/Appearance"
import { Logo } from "@/components/Common/Logo"
import {
  Sidebar,
  SidebarContent,
  SidebarFooter,
  SidebarHeader,
} from "@/components/ui/sidebar"
import useAuth from "@/hooks/useAuth"
import { getSuiteContext } from "@/lib/signalloop-api"
import { cn } from "@/lib/utils"
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
  { icon: Home, title: "Home", path: "/home" },
  { icon: LayoutDashboard, title: "Dashboard", path: "/dashboard" },
  { icon: Briefcase, title: "Campaigns", path: "/campaigns" },
  { icon: BrainCircuit, title: "SignalLoop AI", path: "/signalloop-ai" },
  { icon: Building2, title: "Customer 360", path: "/customer-360" },
  { icon: ListOrdered, title: "Sequences", path: "/sequences" },
  { icon: Mic2, title: "Voice Agents", path: "/voice-agents" },
  { icon: CalendarClock, title: "Meetings", path: "/scheduling" },
  { icon: Users, title: "Contacts", path: "/contacts" },
  { icon: Compass, title: "Lead Discovery", path: "/lead-discovery" },
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

const adminItems: Item[] = [
  { icon: PlugZap, title: "Providers", path: "/settings/providers" },
  {
    icon: AlertTriangle,
    title: "Dead Letters",
    path: "/admin/chatbot/dead-letters",
  },
  { icon: Users, title: "Admin", path: "/admin" },
]

type SectionId = "outreach" | "messaging" | "admin"

type SectionDef = {
  id: SectionId
  label: string
  icon: LucideIcon
}

export function AppSidebar() {
  const { user: currentUser } = useAuth()
  const userWithRole = currentUser as UserWithRole | null | undefined
  const router = useRouterState()
  const currentPath = router.location.pathname

  const suiteContext = useQuery({
    queryKey: ["suite-context"],
    queryFn: () => getSuiteContext(),
    enabled: Boolean(currentUser),
    retry: false,
  })
  const canSignalLoop = suiteContext.data?.products.signalloop.visible ?? true

  const chatbotItems = isChatbotAdmin(userWithRole)
    ? adminChatbotItems
    : agentChatbotItems

  // Detect initial active section based on current path
  const [activeSection, setActiveSection] = useState<SectionId>(() => {
    if (currentPath.startsWith("/chatbot")) return "messaging"
    if (
      (currentPath.startsWith("/admin") ||
        currentPath.startsWith("/platform") ||
        currentPath.startsWith("/settings/providers")) &&
      currentUser?.is_superuser
    ) {
      return "admin"
    }
    return "outreach"
  })

  // Synchronize active section if navigation changes into a different domain
  useEffect(() => {
    if (currentPath.startsWith("/chatbot")) {
      setActiveSection("messaging")
    } else if (
      (currentPath.startsWith("/admin") ||
        currentPath.startsWith("/platform") ||
        currentPath.startsWith("/settings/providers")) &&
      currentUser?.is_superuser
    ) {
      setActiveSection("admin")
    }
  }, [currentPath, currentUser?.is_superuser])

  const sections = useMemo<SectionDef[]>(() => {
    const list: SectionDef[] = [
      { id: "outreach", label: "Outreach", icon: Briefcase },
      { id: "messaging", label: "Messaging", icon: MessageSquare },
    ]
    if (currentUser?.is_superuser) {
      list.push({ id: "admin", label: "Admin", icon: Shield })
    }
    return list
  }, [currentUser?.is_superuser])

  const visibleGroups = useMemo<ItemGroup[]>(() => {
    if (activeSection === "messaging") {
      return [{ title: "Messaging Hub", items: chatbotItems }]
    }
    if (activeSection === "admin" && currentUser?.is_superuser) {
      return [{ title: "Administration", items: adminItems }]
    }

    // Default outreach groups
    const visibleBaseItems = canSignalLoop
      ? baseItems
      : baseItems.filter((item) =>
          ["Revenue OS", "Dashboard", "Contacts"].includes(item.title),
        )
    const byTitle = (titles: string[]) =>
      visibleBaseItems.filter((item) => titles.includes(item.title))

    return [
      {
        title: "Work",
        items: byTitle(["Home", "Dashboard"]),
      },
      {
        title: "Accounts & Discovery",
        items: byTitle([
          "Lead Discovery",
          "Lead Preparation",
          "Customer 360",
          "Contacts",
        ]),
      },
      {
        title: "Campaigns & AI",
        items: byTitle([
          "Campaigns",
          "SignalLoop AI",
          "Sequences",
          "Voice Agents",
          "Meetings",
          "Templates",
        ]),
      },
      {
        title: "Governance",
        items: byTitle(["Analytics", "Controls", "Settings"]),
      },
    ].filter((g) => g.items.length > 0)
  }, [activeSection, canSignalLoop, chatbotItems, currentUser?.is_superuser])

  return (
    <Sidebar
      collapsible="icon"
      role="navigation"
      aria-label="Primary"
      className="border-r border-sidebar-border"
    >
      <SidebarHeader className="px-4 py-3 group-data-[collapsible=icon]:items-center group-data-[collapsible=icon]:px-0">
        <Logo variant="responsive" tone="inverse" />
      </SidebarHeader>

      <SidebarContent className="gap-1 px-1">
        {/* 3-Way Segmented Switcher */}
        <div className="px-2 pb-1 pt-1 group-data-[collapsible=icon]:px-1">
          <div
            className={cn(
              "flex items-center rounded-lg bg-black/30 p-0.5 border border-white/10 shadow-inner",
              "group-data-[collapsible=icon]:flex-col group-data-[collapsible=icon]:gap-1",
            )}
          >
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
                    "flex flex-1 items-center justify-center gap-1.5 rounded-md py-1 text-xs font-medium transition-colors duration-150",
                    "group-data-[collapsible=icon]:w-full group-data-[collapsible=icon]:p-2",
                    isActive
                      ? "bg-white/16 text-white shadow-xs font-semibold border border-white/10"
                      : "text-sidebar-foreground/60 hover:bg-white/8 hover:text-white",
                  )}
                >
                  <Icon className="size-3.5 shrink-0" />
                  <span className="truncate group-data-[collapsible=icon]:hidden">
                    {section.label}
                  </span>
                </button>
              )
            })}
          </div>
        </div>

        <Main groups={visibleGroups} />
      </SidebarContent>

      <SidebarFooter className="gap-1 border-t border-sidebar-border/70 px-3 py-2">
        <SidebarAppearance />
        <User user={currentUser} />
      </SidebarFooter>
    </Sidebar>
  )
}

export default AppSidebar
