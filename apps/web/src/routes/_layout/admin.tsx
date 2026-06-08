import { useSuspenseQuery } from "@tanstack/react-query"
import { createFileRoute, Outlet, redirect, useRouterState } from "@tanstack/react-router"
import { Suspense } from "react"

import { type UserPublic, UsersService } from "@/client"
import AddUser from "@/components/Admin/AddUser"
import { columns, type UserTableData } from "@/components/Admin/columns"
import { DataTable } from "@/components/Common/DataTable"
import PendingUsers from "@/components/Pending/PendingUsers"
import { isChatbotDemoMode } from "@/features/chatbot/demo"
import useAuth from "@/hooks/useAuth"

type UserWithRole = UserPublic & {
  role?: string | null
}

const isDeadLetterOperator = (user: UserWithRole) =>
  Boolean(user.is_superuser || user.role === "operator" || user.role === "super_admin")

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

    if (!user.is_superuser) {
      throw redirect({
        to: "/",
      })
    }
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

  if (pathname !== "/admin") {
    return <Outlet />
  }

  return (
    <div className="flex flex-col gap-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">Users</h1>
          <p className="text-muted-foreground">
            Manage user accounts and permissions
          </p>
        </div>
        <AddUser />
      </div>
      <UsersTable />
    </div>
  )
}
