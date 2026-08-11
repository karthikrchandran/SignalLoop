import { createFileRoute } from "@tanstack/react-router"

export const Route = createFileRoute("/_layout/admin/members")({
  component: TenantMembers,
})

function TenantMembers() {
  return (
    <section className="space-y-2">
      <h1 className="text-2xl font-bold tracking-tight">People and roles</h1>
      <p className="text-sm text-muted-foreground">
        Manage memberships and role bundles for this tenant only.
      </p>
    </section>
  )
}
