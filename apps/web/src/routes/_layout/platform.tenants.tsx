import { createFileRoute } from "@tanstack/react-router"

export const Route = createFileRoute("/_layout/platform/tenants")({
  component: PlatformTenants,
})

function PlatformTenants() {
  return (
    <section className="space-y-2">
      <h1 className="text-2xl font-bold tracking-tight">Tenants</h1>
      <p className="text-sm text-muted-foreground">
        Tenant lifecycle and product provisioning are managed here. Selecting a tenant never grants access to its business data.
      </p>
    </section>
  )
}
