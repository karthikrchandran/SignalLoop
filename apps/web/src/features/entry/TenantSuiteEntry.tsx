import { useQuery } from "@tanstack/react-query"

import { getApiBase } from "@/lib/signalloop-api"

type PublicEntry = {
  display_name: string
  headline: string
  products: string[]
}

async function getPublicEntry(): Promise<PublicEntry | null> {
  const response = await fetch(`${getApiBase()}/api/v1/public/entry`, {
    credentials: "include",
  })
  if (!response.ok) return null
  return (await response.json()) as PublicEntry
}

export function TenantSuiteEntry() {
  const entry = useQuery({
    queryKey: ["public-entry"],
    queryFn: getPublicEntry,
    retry: false,
  })

  if (!entry.data) return null

  return (
    <div className="flex flex-col items-center gap-2 text-center">
      <h1 className="text-2xl font-bold">{entry.data.display_name}</h1>
      <p className="text-sm text-muted-foreground">{entry.data.headline}</p>
      <div className="mt-2 flex flex-wrap justify-center gap-2 text-xs font-medium text-muted-foreground">
        {entry.data.products.map((product) => (
          <span key={product} className="rounded-full border px-2 py-1">
            {product}
          </span>
        ))}
      </div>
    </div>
  )
}
