import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { Loader2, RefreshCw, ServerCog } from "lucide-react"
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
  type ProviderCapability,
  type ProviderOption,
  getProviderOptions,
  getProviderSelections,
  getWorkspaceId,
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

  const updateSelection = useMutation({
    mutationFn: (input: { capability: ProviderCapability; provider: string }) =>
      updateProviderSelection(input, workspaceId),
    onSuccess: async (selection) => {
      setFeedback(`${capabilityLabels[selection.capability]} provider saved.`)
      await queryClient.invalidateQueries({
        queryKey: ["provider-selections", workspaceId],
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
            }}
            disabled={optionsQuery.isFetching || selectionsQuery.isFetching}
          >
            {optionsQuery.isFetching || selectionsQuery.isFetching ? (
              <Loader2 className="mr-2 size-4 animate-spin" />
            ) : (
              <RefreshCw className="mr-2 size-4" />
            )}
            Refresh
          </Button>
        </div>
      </div>

      {feedback && <Alert>{feedback}</Alert>}

      {isLoading && (
        <Card>
          <CardContent className="flex items-center gap-3 py-8 text-sm text-muted-foreground">
            <Loader2 className="size-4 animate-spin" />
            Loading providers...
          </CardContent>
        </Card>
      )}

      {isError && (
        <Alert variant="destructive">
          {error instanceof Error ? error.message : "Could not load providers."}
        </Alert>
      )}

      {!isLoading && !isError && (
        <div className="grid gap-4 lg:grid-cols-3">
          {visibleCapabilities.map((entry) => (
            <CapabilityCard
              key={entry.capability}
              entry={entry}
              selectedProvider={selectionsByCapability.get(entry.capability)}
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
                setFeedback(`${capabilityLabels[entry.capability]} API responded.`)
              }}
            />
          ))}
        </div>
      )}
    </div>
  )
}

function CapabilityCard({
  entry,
  selectedProvider,
  isSaving,
  isTesting,
  workspaceId,
  onSelect,
  onTest,
}: {
  entry: CapabilityOptions
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
          <ProviderStatusBadge selected={selectedProvider} option={selectedOption} />
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

function providerLabel(provider?: string, option?: ProviderOption) {
  if (!provider) {
    return "Not configured"
  }
  return option?.label ?? provider
}
