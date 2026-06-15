import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import {
  CheckCircle2,
  Loader2,
  RefreshCw,
  ServerCog,
  TriangleAlert,
} from "lucide-react"
import { useMemo, useState } from "react"

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
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import {
  type CapabilityOptions,
  getProviderOptions,
  getProviderSelections,
  getSetupOverview,
  getWorkspaceId,
  type ProviderCapability,
  type ProviderOption,
  type SetupIntegration,
  type SetupOverview,
  type SetupWorkerReadiness,
  updateProviderSelection,
} from "@/lib/signalloop-api"

const capabilityOrder: ProviderCapability[] = [
  "email",
  "sms",
  "voice",
  "stt",
  "tts",
  "llm",
]

const capabilityLabels: Record<ProviderCapability, string> = {
  email: "Email",
  sms: "SMS",
  voice: "Voice",
  stt: "STT",
  tts: "TTS",
  llm: "LLM",
}

export default function ProviderSetupPage() {
  const workspaceId = getWorkspaceId()
  const queryClient = useQueryClient()
  const [feedback, setFeedback] = useState<string | null>(null)

  const optionsQuery = useQuery({
    queryKey: ["provider-options", workspaceId],
    queryFn: () => getProviderOptions(workspaceId),
  })

  const selectionsQuery = useQuery({
    queryKey: ["provider-selections", workspaceId],
    queryFn: () => getProviderSelections(workspaceId),
  })

  const overviewQuery = useQuery({
    queryKey: ["setup-overview", workspaceId],
    queryFn: () => getSetupOverview(workspaceId),
    retry: false,
  })

  const updateSelection = useMutation({
    mutationFn: (input: { capability: ProviderCapability; provider: string }) =>
      updateProviderSelection(input, workspaceId),
    onSuccess: async (selection) => {
      setFeedback(`${capabilityLabels[selection.capability]} provider saved.`)
      await queryClient.invalidateQueries({
        queryKey: ["provider-selections", workspaceId],
      })
      await queryClient.invalidateQueries({
        queryKey: ["setup-overview", workspaceId],
      })
    },
    onError: (error) => {
      setFeedback(
        error instanceof Error
          ? error.message
          : "Could not update provider selection.",
      )
    },
  })

  const optionsByCapability = useMemo(() => {
    const entries = optionsQuery.data?.data ?? []
    return new Map(entries.map((entry) => [entry.capability, entry]))
  }, [optionsQuery.data?.data])

  const selectionsByCapability = useMemo(() => {
    const entries = selectionsQuery.data?.data ?? []
    return new Map(entries.map((entry) => [entry.capability, entry.provider]))
  }, [selectionsQuery.data?.data])

  const integrationsByCapability = useMemo(() => {
    const entries = overviewQuery.data?.integrations ?? []
    return new Map(
      entries
        .filter((entry) => entry.capability)
        .map((entry) => [entry.capability as ProviderCapability, entry]),
    )
  }, [overviewQuery.data?.integrations])

  const visibleCapabilities = capabilityOrder
    .map((capability) => optionsByCapability.get(capability))
    .filter(Boolean) as CapabilityOptions[]

  const isLoading = optionsQuery.isLoading || selectionsQuery.isLoading
  const isError = optionsQuery.isError || selectionsQuery.isError
  const error = optionsQuery.error || selectionsQuery.error

  return (
    <div className="flex flex-col gap-6">
      <div className="flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">Provider Setup</h1>
          <p className="text-sm text-muted-foreground">
            Select active providers for this workspace.
          </p>
        </div>
        <div className="flex items-center gap-3">
          <Badge variant="outline">Workspace: {workspaceId}</Badge>
          <Button
            type="button"
            variant="outline"
            size="sm"
            onClick={() => {
              setFeedback(null)
              optionsQuery.refetch()
              selectionsQuery.refetch()
              overviewQuery.refetch()
            }}
            disabled={
              optionsQuery.isFetching ||
              selectionsQuery.isFetching ||
              overviewQuery.isFetching
            }
          >
            {optionsQuery.isFetching ||
            selectionsQuery.isFetching ||
            overviewQuery.isFetching ? (
              <Loader2 className="mr-2 size-4 animate-spin" />
            ) : (
              <RefreshCw className="mr-2 size-4" />
            )}
            Refresh
          </Button>
        </div>
      </div>

      {feedback && <Alert>{feedback}</Alert>}

      {(isLoading || overviewQuery.isLoading) && (
        <Card>
          <CardContent className="flex items-center gap-3 py-8 text-sm text-muted-foreground">
            <Loader2 className="size-4 animate-spin" />
            Loading providers...
          </CardContent>
        </Card>
      )}

      {(isError || overviewQuery.isError) && (
        <Alert variant="destructive">
          {error instanceof Error
            ? error.message
            : overviewQuery.error instanceof Error
              ? overviewQuery.error.message
              : "Could not load provider readiness."}
        </Alert>
      )}

      {!isLoading &&
        !overviewQuery.isLoading &&
        !isError &&
        !overviewQuery.isError && (
          <>
            {overviewQuery.data && (
              <div className="grid gap-4 lg:grid-cols-3">
                <ReadinessSummaryCard
                  title="Core services"
                  items={[
                    { label: "API", ready: overviewQuery.data.health.api },
                    {
                      label: "Postgres",
                      ready: overviewQuery.data.health.postgres,
                    },
                    { label: "Redis", ready: overviewQuery.data.health.redis },
                  ]}
                />
                <WorkerReadinessCard
                  workers={overviewQuery.data.worker_readiness}
                />
                <CallbackStatusCard overview={overviewQuery.data} />
              </div>
            )}

            <div className="grid gap-4 lg:grid-cols-3">
              {visibleCapabilities.map((entry) => (
                <CapabilityCard
                  key={entry.capability}
                  entry={entry}
                  integration={integrationsByCapability.get(entry.capability)}
                  selectedProvider={selectionsByCapability.get(
                    entry.capability,
                  )}
                  isSaving={
                    updateSelection.isPending &&
                    updateSelection.variables?.capability === entry.capability
                  }
                  isTesting={optionsQuery.isFetching}
                  workspaceId={workspaceId}
                  onSelect={(provider) => {
                    setFeedback(null)
                    updateSelection.mutate({
                      capability: entry.capability,
                      provider,
                    })
                  }}
                  onTest={async () => {
                    setFeedback(null)
                    await optionsQuery.refetch()
                    await overviewQuery.refetch()
                    setFeedback(
                      `${capabilityLabels[entry.capability]} API responded.`,
                    )
                  }}
                />
              ))}
            </div>
          </>
        )}
    </div>
  )
}

function CapabilityCard({
  entry,
  integration,
  selectedProvider,
  isSaving,
  isTesting,
  workspaceId,
  onSelect,
  onTest,
}: {
  entry: CapabilityOptions
  integration?: SetupIntegration
  selectedProvider?: string
  isSaving: boolean
  isTesting: boolean
  workspaceId: string
  onSelect: (provider: string) => void
  onTest: () => Promise<void>
}) {
  const label = capabilityLabels[entry.capability]
  const selectedOption = entry.providers.find(
    (provider) => provider.provider === selectedProvider,
  )

  return (
    <Card data-testid={`provider-card-${entry.capability}`}>
      <CardHeader>
        <div className="flex items-start justify-between gap-3">
          <div>
            <CardTitle className="flex items-center gap-2 text-lg">
              <ServerCog className="size-5 text-muted-foreground" />
              {label}
            </CardTitle>
            <CardDescription>
              Current: {providerLabel(selectedProvider, selectedOption)}
            </CardDescription>
          </div>
          <ProviderStatusBadge
            selected={selectedProvider}
            option={selectedOption}
          />
        </div>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="space-y-2">
          <Select
            value={selectedProvider}
            onValueChange={(provider) => {
              if (provider !== selectedProvider) {
                onSelect(provider)
              }
            }}
            disabled={isSaving || entry.providers.length === 0}
          >
            <SelectTrigger
              aria-label={`Provider for ${label}`}
              className="w-full"
            >
              <SelectValue placeholder="Select provider" />
            </SelectTrigger>
            <SelectContent>
              {entry.providers.map((provider) => (
                <SelectItem key={provider.provider} value={provider.provider}>
                  {provider.label}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
          {selectedOption?.free_tier && (
            <p className="text-xs text-muted-foreground">
              {selectedOption.free_tier}
            </p>
          )}
          {integration && (
            <div className="rounded-md border bg-muted/30 p-3 text-sm">
              <div className="flex items-center justify-between gap-3">
                <span className="font-medium">
                  {integration.provider_label ?? integration.label}
                </span>
                <ReadinessBadge ready={integration.configured} />
              </div>
              {Object.entries(integration.config).length > 0 && (
                <dl className="mt-3 space-y-1 text-xs text-muted-foreground">
                  {Object.entries(integration.config).map(([key, value]) => (
                    <div
                      key={key}
                      className="flex items-start justify-between gap-3"
                    >
                      <dt className="font-medium text-foreground">
                        {key.split("_").join(" ")}
                      </dt>
                      <dd className="break-all text-right">{value}</dd>
                    </div>
                  ))}
                </dl>
              )}
              {integration.note && (
                <p className="mt-2 text-xs text-muted-foreground">
                  {integration.note}
                </p>
              )}
            </div>
          )}
        </div>

        {selectedOption?.requires_creds && (
          <p className="rounded-md border bg-muted/30 p-3 text-sm text-muted-foreground">
            Add credentials via API:{" "}
            <code>POST /workspaces/{workspaceId}/provider-credentials</code>
          </p>
        )}

        <Button
          type="button"
          variant="outline"
          size="sm"
          onClick={onTest}
          disabled={isTesting}
        >
          {isTesting ? (
            <Loader2 className="mr-2 size-4 animate-spin" />
          ) : (
            <RefreshCw className="mr-2 size-4" />
          )}
          Test
        </Button>
      </CardContent>
    </Card>
  )
}

function ProviderStatusBadge({
  selected,
  option,
}: {
  selected?: string
  option?: ProviderOption
}) {
  if (!selected) {
    return (
      <Badge className="bg-amber-100 text-amber-900 hover:bg-amber-100">
        Not configured
      </Badge>
    )
  }

  if (option?.local) {
    return (
      <Badge className="bg-emerald-100 text-emerald-900 hover:bg-emerald-100">
        Local
      </Badge>
    )
  }

  return (
    <Badge className="bg-sky-100 text-sky-900 hover:bg-sky-100">Managed</Badge>
  )
}

function ReadinessSummaryCard({
  title,
  items,
}: {
  title: string
  items: Array<{ label: string; ready: boolean }>
}) {
  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-base">{title}</CardTitle>
        <CardDescription>Live readiness reported by the API.</CardDescription>
      </CardHeader>
      <CardContent className="space-y-2">
        {items.map((item) => (
          <div
            key={item.label}
            className="flex items-center justify-between gap-3 rounded-md border p-3 text-sm"
          >
            <span className="font-medium">{item.label}</span>
            <ReadinessBadge ready={item.ready} />
          </div>
        ))}
      </CardContent>
    </Card>
  )
}

function WorkerReadinessCard({ workers }: { workers: SetupWorkerReadiness[] }) {
  return (
    <Card data-testid="provider-worker-readiness">
      <CardHeader>
        <CardTitle className="text-base">Workers</CardTitle>
        <CardDescription>
          Background worker readiness for selected providers.
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-2">
        {workers.map((worker) => (
          <div key={worker.key} className="rounded-md border p-3 text-sm">
            <div className="flex items-center justify-between gap-3">
              <span className="font-medium">{worker.label}</span>
              <ReadinessBadge ready={worker.ready} />
            </div>
            <p className="mt-1 text-xs text-muted-foreground">
              {formatWorkerDetail(worker)}
            </p>
          </div>
        ))}
      </CardContent>
    </Card>
  )
}

function CallbackStatusCard({ overview }: { overview: SetupOverview }) {
  return (
    <Card data-testid="provider-callback-status">
      <CardHeader>
        <CardTitle className="text-base">Callback host</CardTitle>
        <CardDescription>
          Provider webhooks use this external base URL.
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-3 text-sm">
        <div className="flex items-center justify-between gap-3 rounded-md border p-3">
          <span className="font-medium">Base URL</span>
          <Badge
            className={
              overview.callbacks.public_host
                ? "bg-emerald-100 text-emerald-900 hover:bg-emerald-100"
                : "bg-amber-100 text-amber-900 hover:bg-amber-100"
            }
          >
            {overview.callbacks.public_host ? "Public" : "Local only"}
          </Badge>
        </div>
        <p className="break-all text-muted-foreground">
          {overview.callbacks.public_base_url}
        </p>
      </CardContent>
    </Card>
  )
}

function ReadinessBadge({ ready }: { ready: boolean }) {
  return ready ? (
    <Badge className="gap-1 bg-emerald-100 text-emerald-900 hover:bg-emerald-100">
      <CheckCircle2 className="size-3" />
      Ready
    </Badge>
  ) : (
    <Badge className="gap-1 bg-amber-100 text-amber-900 hover:bg-amber-100">
      <TriangleAlert className="size-3" />
      Missing setup
    </Badge>
  )
}

function formatWorkerDetail(worker: SetupWorkerReadiness) {
  const parts: string[] = []
  if (worker.last_error_message) {
    parts.push(`Error: ${worker.last_error_message}`)
  }
  if (!worker.running) {
    parts.push(
      worker.last_seen_at ? "Heartbeat stale" : "Waiting for worker heartbeat",
    )
  }
  if (worker.status && worker.status !== "healthy") {
    parts.push(`Status: ${worker.status}`)
  }
  if (worker.last_seen_at) {
    parts.push(`Last seen: ${new Date(worker.last_seen_at).toLocaleString()}`)
  }
  if (worker.missing.length > 0) {
    parts.push(
      `Missing: ${worker.missing.map((item) => item.split("_").join(" ")).join(", ")}`,
    )
  }
  if (parts.length === 0) {
    return "Running with required providers."
  }
  return `${parts.join(" | ")}.`
}

function providerLabel(provider?: string, option?: ProviderOption) {
  if (!provider) {
    return "Not configured"
  }
  return option?.label ?? provider
}
