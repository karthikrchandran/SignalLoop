import { Link } from "@tanstack/react-router"

import type { SuiteContext } from "@/lib/signalloop-api"

const labels = {
  commitarc: "CommitArc",
  revenueos: "RevenueOS",
  signalloop: "SignalLoop",
} as const

export function ProductSwitcher({ context }: { context: SuiteContext }) {
  return (
    <nav aria-label="Products" className="flex flex-wrap gap-2">
      {Object.entries(context.products).flatMap(([product, details]) => {
        if (!details.visible || !details.href) return []
        return (
          <Link
            key={product}
            to={details.href as never}
            className="rounded-md border border-border bg-background px-3 py-2 text-sm font-medium hover:border-primary/60 hover:text-primary"
          >
            {labels[product as keyof typeof labels]}
            {details.mode === "ESSENTIALS" ? " Essentials" : ""}
          </Link>
        )
      })}
    </nav>
  )
}
