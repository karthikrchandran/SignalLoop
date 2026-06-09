import {
  Building2,
  ExternalLink,
  Loader2,
  RefreshCw,
  Search,
} from "lucide-react"
import { useCallback, useEffect, useState } from "react"

import { Alert } from "@/components/ui/alert"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"
import { type Customer360AccountRow, listCustomer360Accounts } from "./api"

const channelLabels: Record<string, string> = {
  chatbot: "Chatbot",
  email: "Email",
  voice: "Voice",
  prospecting: "Prospecting",
}

const channelOrder = ["chatbot", "email", "voice", "prospecting"]

function pluralizeContacts(count: number) {
  return `${count} contact${count === 1 ? "" : "s"}`
}

function channelCount(account: Customer360AccountRow, channel: string) {
  return account.channel_counts[channel] ?? 0
}

function formatStatus(status: string) {
  return status
    .split("_")
    .filter(Boolean)
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(" ")
}

function formatLastActivity(value?: string | null) {
  if (!value) return "-"

  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return "-"

  return new Intl.DateTimeFormat("en", {
    month: "short",
    day: "numeric",
    hour: "numeric",
    minute: "2-digit",
  }).format(date)
}

export default function Customer360AccountsPage() {
  const [accounts, setAccounts] = useState<Customer360AccountRow[]>([])
  const [count, setCount] = useState(0)
  const [search, setSearch] = useState("")
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState("")

  const loadAccounts = useCallback(async (nextSearch = "") => {
    setLoading(true)
    setError("")

    try {
      const response = await listCustomer360Accounts(nextSearch)
      setAccounts(response.data)
      setCount(response.count)
    } catch (requestError) {
      setError(
        requestError instanceof Error
          ? requestError.message
          : "Could not load accounts",
      )
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    void loadAccounts("")
  }, [loadAccounts])

  return (
    <div className="flex flex-col gap-6">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <div className="mb-2 flex items-center gap-2 text-sm text-muted-foreground">
            <Building2 className="size-4" />
            Account workspace
          </div>
          <h1 className="text-3xl font-semibold tracking-tight">
            Customer 360
          </h1>
          <p className="text-sm text-muted-foreground">
            {count} account{count === 1 ? "" : "s"} in the active workspace
          </p>
        </div>
        <Button
          variant="outline"
          onClick={() => void loadAccounts(search)}
          disabled={loading}
        >
          {loading ? (
            <Loader2 className="mr-2 size-4 animate-spin" />
          ) : (
            <RefreshCw className="mr-2 size-4" />
          )}
          Refresh
        </Button>
      </div>

      {error && (
        <Alert variant="destructive">
          <p className="text-sm">{error}</p>
        </Alert>
      )}

      <Card>
        <CardHeader>
          <CardTitle>Accounts</CardTitle>
          <CardDescription>
            Review account-level contacts, channel activity, and next action.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="flex flex-wrap gap-2">
            <div className="relative min-w-72 flex-1">
              <Search className="absolute left-3 top-1/2 size-4 -translate-y-1/2 text-muted-foreground" />
              <Input
                value={search}
                onChange={(event) => setSearch(event.target.value)}
                onKeyDown={(event) => {
                  if (event.key === "Enter") void loadAccounts(search)
                }}
                className="pl-9"
                placeholder="Search accounts"
              />
            </div>
            <Button
              type="button"
              variant="outline"
              onClick={() => void loadAccounts(search)}
              disabled={loading}
            >
              Search
            </Button>
          </div>

          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Account</TableHead>
                <TableHead>Status</TableHead>
                <TableHead>Contacts</TableHead>
                <TableHead>Channels</TableHead>
                <TableHead>Last activity</TableHead>
                <TableHead>Next action</TableHead>
                <TableHead className="text-right">Open</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {loading && accounts.length === 0 ? (
                <TableRow>
                  <TableCell
                    colSpan={7}
                    className="py-10 text-center text-muted-foreground"
                  >
                    <span className="inline-flex items-center gap-2">
                      <Loader2 className="size-4 animate-spin" />
                      Loading accounts...
                    </span>
                  </TableCell>
                </TableRow>
              ) : accounts.length === 0 ? (
                <TableRow>
                  <TableCell
                    colSpan={7}
                    className="py-10 text-center text-muted-foreground"
                  >
                    No accounts found.
                  </TableCell>
                </TableRow>
              ) : (
                accounts.map((account) => (
                  <TableRow key={account.id}>
                    <TableCell>
                      <div className="min-w-56">
                        <p className="font-medium">{account.name}</p>
                        <p className="text-xs text-muted-foreground">
                          {account.industry || account.website_url || "-"}
                        </p>
                      </div>
                    </TableCell>
                    <TableCell>
                      <Badge variant="secondary">
                        {formatStatus(account.status)}
                      </Badge>
                    </TableCell>
                    <TableCell>
                      {pluralizeContacts(account.contact_count)}
                    </TableCell>
                    <TableCell>
                      <div className="flex min-w-72 flex-wrap gap-1.5">
                        {channelOrder.map((channel) => (
                          <Badge key={channel} variant="outline">
                            {channelLabels[channel]}{" "}
                            {channelCount(account, channel)}
                          </Badge>
                        ))}
                      </div>
                    </TableCell>
                    <TableCell>
                      {formatLastActivity(account.last_activity_at)}
                    </TableCell>
                    <TableCell>
                      <p className="max-w-72 truncate">
                        {account.top_next_action || "No action queued"}
                      </p>
                    </TableCell>
                    <TableCell className="text-right">
                      <Button asChild variant="outline" size="sm">
                        <a
                          href={`/customer-360/${account.id}`}
                          aria-label={`Open ${account.name}`}
                        >
                          <ExternalLink className="size-4" />
                          Open
                        </a>
                      </Button>
                    </TableCell>
                  </TableRow>
                ))
              )}
            </TableBody>
          </Table>
        </CardContent>
      </Card>
    </div>
  )
}
