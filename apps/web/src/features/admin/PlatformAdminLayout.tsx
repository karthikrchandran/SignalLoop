import type { PropsWithChildren } from "react"

const platformLinks = [
  { label: "Tenants", href: "/platform/tenants" },
  { label: "Products", href: "/platform/products" },
  { label: "Identity", href: "/platform/identity" },
  { label: "Messaging defaults", href: "/platform/messaging" },
  { label: "Provider policies", href: "/platform/provider-policies" },
  { label: "Usage and health", href: "/platform/usage-health" },
  { label: "Support access", href: "/platform/support-access" },
  { label: "Audit", href: "/platform/audit" },
]

export function PlatformAdminLayout({ children }: PropsWithChildren) {
  return (
    <div className="space-y-6">
      <section>
        <h1 className="text-2xl font-bold tracking-tight">Platform administration</h1>
        <p className="mt-1 text-sm text-muted-foreground">
          Manage suite tenants and policy. Tenant business data requires a separate, time-bounded support grant.
        </p>
      </section>
      <nav aria-label="Platform administration" className="grid gap-2 sm:grid-cols-2 lg:grid-cols-4">
        {platformLinks.map((link) => (
          <a key={link.label} href={link.href} className="rounded-md border bg-card px-3 py-2 text-sm font-medium hover:border-primary/60 hover:text-primary">
            {link.label}
          </a>
        ))}
      </nav>
      {children}
    </div>
  )
}
