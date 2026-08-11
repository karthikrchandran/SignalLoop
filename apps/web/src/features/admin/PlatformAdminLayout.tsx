const platformLinks = [
  "Tenants",
  "Products",
  "Identity",
  "Messaging defaults",
  "Provider policies",
  "Usage and health",
  "Support access",
  "Audit",
]

export function PlatformAdminLayout() {
  return (
    <div className="space-y-6">
      <section>
        <h1 className="text-2xl font-bold tracking-tight">Platform administration</h1>
        <p className="mt-1 text-sm text-muted-foreground">
          Manage suite tenants and policy. Tenant business data requires a separate, time-bounded support grant.
        </p>
      </section>
      <nav aria-label="Platform administration" className="grid gap-2 sm:grid-cols-2 lg:grid-cols-4">
        {platformLinks.map((label) => (
          <a key={label} href="#platform-workspace" className="rounded-md border bg-card px-3 py-2 text-sm font-medium hover:border-primary/60 hover:text-primary">
            {label}
          </a>
        ))}
      </nav>
      <section id="platform-workspace" className="rounded-lg border bg-card p-5">
        <h2 className="text-lg font-semibold">Control-plane workspace</h2>
        <p className="mt-2 text-sm text-muted-foreground">
          Select a control-plane area to manage tenant lifecycle, product access, identity configuration, and audited support access.
        </p>
      </section>
    </div>
  )
}
