import { Link } from "@tanstack/react-router"
import { ArrowRight, CircleAlert, ListChecks, Sparkles } from "lucide-react"

import { ProductSwitcher } from "@/features/suite/ProductSwitcher"
import { useSuiteContext } from "@/features/suite/useSuiteContext"

export function SuiteHomePage() {
  const suiteContext = useSuiteContext()

  if (suiteContext.isLoading) {
    return <p className="text-sm text-muted-foreground">Loading your workspace…</p>
  }

  if (!suiteContext.data) {
    return (
      <section className="rounded-lg border border-border bg-card p-6">
        <h1 className="text-xl font-semibold">Workspace unavailable</h1>
        <p className="mt-2 text-sm text-muted-foreground">
          Your product access could not be resolved. Ask a tenant administrator to check your membership.
        </p>
      </section>
    )
  }

  const { products, tenant } = suiteContext.data
  const canManageCampaigns = products.signalloop.visible

  return (
    <div className="space-y-6">
      <section className="rounded-xl border border-primary/30 bg-gradient-to-br from-primary/15 via-background to-background p-6 sm:p-8">
        <p className="text-sm font-medium text-primary">{tenant.display_name}</p>
        <h1 className="mt-2 text-3xl font-semibold tracking-tight">What needs attention</h1>
        <p className="mt-3 max-w-2xl text-sm leading-6 text-muted-foreground">
          Your workspace is tailored to the products and responsibilities assigned to you.
        </p>
        <div className="mt-5">
          <ProductSwitcher context={suiteContext.data} />
        </div>
      </section>

      <section className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
        <article className="rounded-lg border bg-card p-5">
          <ListChecks className="size-5 text-primary" />
          <h2 className="mt-3 text-lg font-semibold">My pipeline</h2>
          <p className="mt-2 text-sm text-muted-foreground">
            Review the commitments, follow-ups, and risks assigned to you in CommitArc.
          </p>
          {products.commitarc.visible ? (
            <Link className="mt-4 inline-flex items-center gap-2 text-sm font-medium text-primary" to={products.commitarc.href as never}>
              Open CommitArc <ArrowRight className="size-4" />
            </Link>
          ) : null}
        </article>
        <article className="rounded-lg border bg-card p-5">
          <Sparkles className="size-5 text-primary" />
          <h2 className="mt-3 text-lg font-semibold">Recommended next actions</h2>
          <p className="mt-2 text-sm text-muted-foreground">
            RevenueOS Essentials highlights the next safe action using only records you may access.
          </p>
          {products.revenueos.visible ? <p className="mt-4 text-sm font-medium text-primary">RevenueOS {products.revenueos.mode === "ESSENTIALS" ? "Essentials" : ""}</p> : null}
        </article>
        <article className="rounded-lg border bg-card p-5">
          <CircleAlert className="size-5 text-primary" />
          <h2 className="mt-3 text-lg font-semibold">Products</h2>
          <p className="mt-2 text-sm text-muted-foreground">
            Products without an active entitlement are not shown or reachable from this workspace.
          </p>
          {canManageCampaigns ? (
            <Link className="mt-4 inline-flex items-center gap-2 text-sm font-medium text-primary" to="/campaigns">
              Open campaigns <ArrowRight className="size-4" />
            </Link>
          ) : null}
        </article>
      </section>
    </div>
  )
}
