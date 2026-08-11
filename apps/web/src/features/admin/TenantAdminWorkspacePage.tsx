type TenantAdminWorkspacePageProps = {
  title: string
  description: string
  sections: string[]
}

export function TenantAdminWorkspacePage({
  title,
  description,
  sections,
}: TenantAdminWorkspacePageProps) {
  return (
    <section className="rounded-lg border bg-card p-5">
      <h1 className="text-2xl font-bold tracking-tight">{title}</h1>
      <p className="mt-2 text-sm text-muted-foreground">{description}</p>
      <ul className="mt-4 grid gap-2 text-sm sm:grid-cols-2">
        {sections.map((section) => (
          <li key={section} className="rounded-md border px-3 py-2 text-muted-foreground">
            {section}
          </li>
        ))}
      </ul>
    </section>
  )
}
