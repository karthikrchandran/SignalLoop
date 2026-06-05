import {
  BarChart3,
  Briefcase,
  FileText,
  Home,
  ListOrdered,
  Mic2,
  PlugZap,
  Settings,
  Shield,
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
import { type Item, Main } from "./Main"
import { User } from "./User"

const baseItems: Item[] = [
  { icon: Home, title: "Dashboard", path: "/" },
  { icon: Briefcase, title: "Campaigns", path: "/campaigns" },
  { icon: ListOrdered, title: "Sequences", path: "/sequences" },
  { icon: Mic2, title: "Voice Agents", path: "/voice-agents" },
  { icon: Users, title: "Contacts", path: "/contacts" },
  { icon: BarChart3, title: "Analytics", path: "/analytics" },
  { icon: FileText, title: "Templates", path: "/templates" },
  { icon: Shield, title: "Controls", path: "/controls" },
  { icon: Settings, title: "Settings", path: "/settings" },
]

export function AppSidebar() {
  const { user: currentUser } = useAuth()

  const items = currentUser?.is_superuser
    ? [
        ...baseItems,
        { icon: PlugZap, title: "Providers", path: "/settings/providers" },
        { icon: Users, title: "Admin", path: "/admin" },
      ]
    : baseItems

  return (
    <Sidebar collapsible="icon">
      <SidebarHeader className="px-4 py-6 group-data-[collapsible=icon]:px-0 group-data-[collapsible=icon]:items-center">
        <Logo variant="responsive" />
      </SidebarHeader>
      <SidebarContent>
        <Main items={items} />
      </SidebarContent>
      <SidebarFooter>
        <SidebarAppearance />
        <User user={currentUser} />
      </SidebarFooter>
    </Sidebar>
  )
}

export default AppSidebar
