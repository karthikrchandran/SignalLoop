const tenantLinks = [
  { label: "People and roles", href: "/admin/members" },
  { label: "Products", href: "#tenant-workspace" },
  { label: "Branding", href: "#tenant-workspace" },
  { label: "Security", href: "#tenant-workspace" },
  { label: "Messaging", href: "#tenant-workspace" },
  { label: "Tenant audit", href: "#tenant-workspace" },
]

export function TenantAdminLayout() {
  return (
    <section className="space-y-4">
      <div>
        <h1 className="text-2xl font-bold tracking-tight">Tenant administration</h1>
        <p className="mt-1 text-sm text-muted-foreground">
          Manage only your tenant’s members, products, branding, and security settings.
        </p>
      </div>
      <nav aria-label="Tenant administration" className="flex flex-wrap gap-2">
        {tenantLinks.map((link) => (
          <a key={link.label} href={link.href} className="rounded-md border bg-card px-3 py-2 text-sm font-medium hover:border-primary/60 hover:text-primary">
            {link.label}
          </a>
        ))}
      </nav>
    </section>
  )
}
