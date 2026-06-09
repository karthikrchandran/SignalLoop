import { engagehubRequest } from "@/lib/engagehub-api"

export type Customer360Account = {
  id: string
  workspace_id: string
  name: string
  account_key: string
  website_url?: string | null
  industry?: string | null
  status: string
  summary?: string | null
  tags: string[]
  created_at: string
  updated_at: string
}

export type Customer360AccountRow = Customer360Account & {
  contact_count: number
  last_activity_at?: string | null
  channel_counts: Record<string, number>
  top_next_action?: string | null
}

export type Customer360AccountsResponse = {
  data: Customer360AccountRow[]
  count: number
}

export function listCustomer360Accounts(search = "") {
  const params = new URLSearchParams({ limit: "50" })
  if (search.trim()) params.set("search", search.trim())

  return engagehubRequest<Customer360AccountsResponse>(
    `/api/v1/customer-360/accounts?${params.toString()}`,
  )
}
