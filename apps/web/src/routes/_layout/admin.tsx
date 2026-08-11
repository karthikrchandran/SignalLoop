import { useSuspenseQuery } from "@tanstack/react-query"
import { createFileRoute, Outlet, redirect, useRouterState } from "@tanstack/react-router"
import { Suspense } from "react"

import { type UserPublic, UsersService } from "@/client"
import AddUser from "@/components/Admin/AddUser"
import { columns, type UserTableData } from "@/components/Admin/columns"
import { DataTable } from "@/components/Common/DataTable"
import PendingUsers from "@/components/Pending/PendingUsers"
import { TenantAdminLayout } from "@/features/admin/TenantAdminLayout"
import { TenantAdminWorkspacePage } from "@/features/admin/TenantAdminWorkspacePage"
import { isChatbotDemoMode } from "@/features/chatbot/demo"
import useAuth from "@/hooks/useAuth"
import { getSuiteContext } from "@/lib/signalloop-api"

type UserWithRole = UserPublic & {
  role?: string | null
}

const isDeadLetterOperator = (user: UserWithRole) =>
  Boolean(user.is_superuser || user.role === "operator" || user.role === "super_admin")

const tenantAdminCapabilities = new Set([
  "tenant.members.manage",
  "tenant.settings.manage",
  "revenueos.admin.manage",
  "commitarc.admin.manage",
  "signalloop.admin.manage",
])

function getUsersQueryOptions() {
  return {
    queryFn: () => UsersService.readUsers({ skip: 0, limit: 100 }),
    queryKey: ["users"],
  }
}

export const Route = createFileRoute("/_layout/admin")({
  component: Admin,
  beforeLoad: async ({ location }) => {
    if (isChatbotDemoMode() && location.pathname === "/admin/chatbot/dead-letters") {
      return
    }
    const user = await UsersService.readUserMe() as UserWithRole
    const isDeadLettersRoute = location.pathname === "/admin/chatbot/dead-letters"
    if (isDeadLettersRoute && isDeadLetterOperator(user)) {
      return
    }

    if (user.is_superuser) {
      return
    }

    try {
      const suiteContext = await getSuiteContext()
      if (suiteContext.capabilities.some((capability) => tenantAdminCapabilities.has(capability))) {
        return
      }
    } catch {
      // The suite context endpoint is the authoritative tenant membership check.
    }

    throw redirect({
      to: "/",
    })
  },
  head: () => ({
    meta: [
      {
        title: "Admin - FastAPI Template",
      },
    ],
  }),
})

function UsersTableContent() {
  const { user: currentUser } = useAuth()
  const { data: users } = useSuspenseQuery(getUsersQueryOptions())

  const tableData: UserTableData[] = users.data.map((user: UserPublic) => ({
    ...user,
    isCurrentUser: currentUser?.id === user.id,
  }))

  return <DataTable columns={columns} data={tableData} />
}

function UsersTable() {
  return (
    <Suspense fallback={<PendingUsers />}>
      <UsersTableContent />
    </Suspense>
  )
}

function Admin() {
  const pathname = useRouterState({ select: (state) => state.location.pathname })
  const { user } = useAuth()

  if (pathname !== "/admin") {
    return (
      <TenantAdminLayout>
        <Outlet />
      </TenantAdminLayout>
    )
  }

  if (!user?.is_superuser) {
    return (
      <TenantAdminLayout>
        <TenantAdminWorkspacePage
          title="Tenant overview"
          description="Manage your tenant's people, enabled products, brand, security, and messaging settings."
          sections={["People and roles", "Products", "Security and messaging", "Tenant audit"]}
        />
      </TenantAdminLayout>
    )
  }

  return (
    <TenantAdminLayout>
      <div id="tenant-workspace" className="flex items-center justify-between">
        <div>
          <h2 className="text-xl font-bold tracking-tight">Users</h2>
          <p className="text-muted-foreground">
            Manage user accounts and permissions
          </p>
        </div>
        <AddUser />
      </div>
      <UsersTable />
    </TenantAdminLayout>
  )
}
