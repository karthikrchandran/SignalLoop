import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { createFileRoute, Outlet, useRouterState } from "@tanstack/react-router"
import { CheckCircle2, Loader2, RefreshCw, TriangleAlert } from "lucide-react"
import { useMemo, useState } from "react"

import ChangePassword from "@/components/UserSettings/ChangePassword"
import DeleteAccount from "@/components/UserSettings/DeleteAccount"
import UserInformation from "@/components/UserSettings/UserInformation"
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
import { Label } from "@/components/ui/label"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { OptOutsTab } from "@/features/chatbot/OptOutsTab"
import useAuth from "@/hooks/useAuth"
import { engagehubRequest, getWorkspaceId } from "@/lib/engagehub-api"

type SetupIntegration = {
  key: string
  label: string
  configured: boolean
  source: string
  editable: boolean
  has_secret: boolean
  config: Record<string, string>
  note?: string | null
}

type SetupWorkerReadiness = {
  key: string
  label: string
  ready: boolean
  running: boolean
  status: string
  last_seen_at?: string | null
  last_error_message?: string | null
  missing: string[]
}

type SetupOverview = {
  workspace_id: string
  health: {
    api: boolean
    postgres: boolean
    redis: boolean
  }
  integrations: SetupIntegration[]
  worker_readiness: SetupWorkerReadiness[]
  callbacks: {
    server_host: string
    public_base_url: string
    public_host: boolean
    sendgrid_webhook_url: string
    twilio_twiml_url: string
    twilio_status_url: string
    twilio_recording_url: string
    twilio_media_stream_url: string
  }
}

type CredentialFormState = {
  apiKey: string
  apiSecret: string
  configValue: string
}

type RuntimeConfigFormState = {
  deepgramApiKey: string
  groqApiKey: string
  teamNotificationEmail: string
}

const tabsConfig = [
  { value: "my-profile", title: "My profile", component: UserInformation },
  { value: "password", title: "Password", component: ChangePassword },
  { value: "danger-zone", title: "Danger zone", component: DeleteAccount },
]

const emptyCredentialForm = (): CredentialFormState => ({
  apiKey: "",
  apiSecret: "",
  configValue: "",
})

const emptyRuntimeConfigForm = (): RuntimeConfigFormState => ({
  deepgramApiKey: "",
  groqApiKey: "",
  teamNotificationEmail: "",
})

const canManageChatbotOptOuts = (user?: { is_superuser?: boolean; role?: string | null } | null) =>
  Boolean(user?.is_superuser || user?.role === "admin" || user?.role === "super_admin")

export const Route = createFileRoute("/_layout/settings")({
  component: UserSettings,
  head: () => ({
    meta: [
      {
        title: "Settings - FastAPI Template",
      },
    ],
  }),
})

function UserSettings() {
  const pathname = useRouterState({ select: (state) => state.location.pathname })
  const { user: currentUser, isLoading, isError, error } = useAuth()
  const currentUserWithRole = currentUser as ({ is_superuser?: boolean; role?: string | null } & typeof currentUser) | null | undefined
  const finalTabs = useMemo(() => {
    const baseTabs = currentUserWithRole?.is_superuser
      ? tabsConfig.filter((tab) => tab.value !== "danger-zone")
      : tabsConfig

    const chatbotTabs = canManageChatbotOptOuts(currentUserWithRole)
      ? [
          {
            value: "opt-outs",
            title: "Opt-outs",
            component: OptOutsTab,
          },
        ]
      : []

    const superuserTabs = currentUserWithRole?.is_superuser
      ? [
          {
            value: "workspace-setup",
            title: "Workspace setup",
            component: WorkspaceSetupTab,
          },
        ]
      : []

    return [...baseTabs, ...chatbotTabs, ...superuserTabs]
  }, [currentUserWithRole?.is_superuser, currentUserWithRole?.role])

  if (pathname !== "/settings") {
    return <Outlet />
  }

  return (
    <div className="flex flex-col gap-6">
      <div>
        <h1 className="text-2xl font-bold tracking-tight">User Settings</h1>
        <p className="text-muted-foreground">
          Manage your account settings and preferences
        </p>
      </div>

      {isLoading && (
        <Card>
          <CardContent className="flex items-center gap-3 py-8 text-sm text-muted-foreground">
            <Loader2 className="size-4 animate-spin" />
            Loading settings...
          </CardContent>
        </Card>
      )}

      {!isLoading && (isError || !currentUser) && (
        <Alert variant="destructive">
          {error instanceof Error ? error.message : "Could not load your settings."}
        </Alert>
      )}

      {currentUser && (
        <Tabs defaultValue="my-profile">
          <TabsList className="flex h-auto flex-wrap items-center gap-2">
            {finalTabs.map((tab) => (
              <TabsTrigger key={tab.value} value={tab.value}>
                {tab.title}
              </TabsTrigger>
            ))}
          </TabsList>
          {finalTabs.map((tab) => (
            <TabsContent key={tab.value} value={tab.value}>
              <tab.component />
            </TabsContent>
          ))}
        </Tabs>
      )}
    </div>
  )
}

function WorkspaceSetupTab() {
  const workspaceId = getWorkspaceId()
  const queryClient = useQueryClient()
  const [sendgridForm, setSendgridForm] = useState<CredentialFormState>(emptyCredentialForm)
  const [twilioForm, setTwilioForm] = useState<CredentialFormState>(emptyCredentialForm)
  const [runtimeForm, setRuntimeForm] = useState<RuntimeConfigFormState>(emptyRuntimeConfigForm)
  const [feedback, setFeedback] = useState<string | null>(null)

  const overviewQuery = useQuery({
    queryKey: ["workspace-setup", workspaceId],
    queryFn: () => engagehubRequest<SetupOverview>("/api/v1/utils/setup-overview/"),
  })

  const upsertCredential = useMutation({
    mutationFn: async (input: {
      provider: "sendgrid" | "twilio"
      channel: "email" | "voice"
      apiKey: string
      apiSecret: string
      config: Record<string, string>
    }) => {
      await engagehubRequest(`/api/v1/workspaces/${workspaceId}/provider-credentials`, {
        method: "POST",
        body: {
          provider: input.provider,
          channel: input.channel,
          api_key: input.apiKey,
          api_secret: input.apiSecret || undefined,
          config_json: input.config,
        },
      })
    },
    onSuccess: async (_, variables) => {
      setFeedback(`${variables.provider === "sendgrid" ? "SendGrid" : "Twilio"} credentials saved.`)
      if (variables.provider === "sendgrid") {
        setSendgridForm((current) => ({ ...current, apiKey: "", apiSecret: "" }))
      } else {
        setTwilioForm((current) => ({ ...current, apiKey: "", apiSecret: "" }))
      }
      await queryClient.invalidateQueries({ queryKey: ["workspace-setup", workspaceId] })
    },
    onError: (mutationError) => {
      setFeedback(mutationError instanceof Error ? mutationError.message : "Could not save provider credentials.")
    },
  })

  const upsertRuntimeConfig = useMutation({
    mutationFn: async () => {
      const body: Record<string, string> = {}
      if (runtimeForm.deepgramApiKey.trim()) {
        body.deepgram_api_key = runtimeForm.deepgramApiKey.trim()
      }
      if (runtimeForm.groqApiKey.trim()) {
        body.groq_api_key = runtimeForm.groqApiKey.trim()
      }
      if (runtimeForm.teamNotificationEmail.trim()) {
        body.team_notification_email = runtimeForm.teamNotificationEmail.trim()
      }
      if (Object.keys(body).length === 0) {
        throw new Error("Enter at least one runtime setting to save.")
      }

      await engagehubRequest(`/api/v1/workspaces/${workspaceId}/runtime-config`, {
        method: "POST",
        body,
      })
    },
    onSuccess: async () => {
      setFeedback("Runtime services saved.")
      setRuntimeForm(emptyRuntimeConfigForm())
      await queryClient.invalidateQueries({ queryKey: ["workspace-setup", workspaceId] })
    },
    onError: (mutationError) => {
      setFeedback(mutationError instanceof Error ? mutationError.message : "Could not save runtime services.")
    },
  })

  const integrationMap = useMemo(() => {
    const entries = overviewQuery.data?.integrations ?? []
    return new Map(entries.map((integration) => [integration.key, integration]))
  }, [overviewQuery.data?.integrations])

  const sendgrid = integrationMap.get("sendgrid")
  const twilio = integrationMap.get("twilio")
  const deepgram = integrationMap.get("deepgram")
  const groq = integrationMap.get("groq")
  const teamNotifications = integrationMap.get("team_notifications")

  return (
    <div className="space-y-6">
      <div className="flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
        <div>
          <h2 className="text-xl font-semibold tracking-tight">Workspace setup</h2>
          <p className="text-sm text-muted-foreground">
            Configure delivery providers, verify runtime dependencies, and confirm callback URLs for this workspace.
          </p>
        </div>
        <div className="flex items-center gap-3">
          <Badge variant="outline">Workspace: {workspaceId}</Badge>
          <Button
            type="button"
            variant="outline"
            size="sm"
            onClick={() => overviewQuery.refetch()}
            disabled={overviewQuery.isFetching}
          >
            {overviewQuery.isFetching ? <Loader2 className="mr-2 size-4 animate-spin" /> : <RefreshCw className="mr-2 size-4" />}
            Refresh
          </Button>
        </div>
      </div>

      {feedback && <Alert>{feedback}</Alert>}

      {overviewQuery.isLoading && (
        <Card>
          <CardContent className="flex items-center gap-3 py-8 text-sm text-muted-foreground">
            <Loader2 className="size-4 animate-spin" />
            Loading workspace setup...
          </CardContent>
        </Card>
      )}

      {overviewQuery.isError && (
        <Alert variant="destructive">
          {overviewQuery.error instanceof Error
            ? overviewQuery.error.message
            : "Could not load workspace setup."}
        </Alert>
      )}

      {overviewQuery.data && (
        <>
          {!overviewQuery.data.callbacks.public_host && (
            <Alert variant="destructive">
              Callback host is still local. Twilio and SendGrid webhooks need a publicly reachable base URL before end-to-end delivery can work.
            </Alert>
          )}

          <div className="grid gap-4 xl:grid-cols-3">
            <SetupStatusCard
              title="Core dependencies"
              description="Live API checks from the current server process."
              items={[
                { label: "API", ready: overviewQuery.data.health.api },
                { label: "Postgres", ready: overviewQuery.data.health.postgres },
                { label: "Redis", ready: overviewQuery.data.health.redis },
              ]}
            />
            <SetupStatusCard
              title="Workers"
              description="Derived readiness for the background workers needed to run campaigns."
              items={overviewQuery.data.worker_readiness.map((worker) => ({
                label: worker.label,
                ready: worker.ready,
                detail: buildWorkerDetail(worker),
              }))}
            />
            <Card>
              <CardHeader>
                <CardTitle>Callback host</CardTitle>
                <CardDescription>External URLs that providers must call back into.</CardDescription>
              </CardHeader>
              <CardContent className="space-y-3 text-sm">
                <div className="flex items-center justify-between gap-3 rounded-md border p-3">
                  <span className="font-medium">Base URL</span>
                  <StatusBadge ready={overviewQuery.data.callbacks.public_host} />
                </div>
                <p className="break-all text-muted-foreground">{overviewQuery.data.callbacks.public_base_url}</p>
                <UrlRow label="SendGrid webhook" value={overviewQuery.data.callbacks.sendgrid_webhook_url} />
                <UrlRow label="Twilio TwiML" value={overviewQuery.data.callbacks.twilio_twiml_url} />
                <UrlRow label="Twilio status" value={overviewQuery.data.callbacks.twilio_status_url} />
                <UrlRow label="Twilio recording" value={overviewQuery.data.callbacks.twilio_recording_url} />
                <UrlRow label="Twilio media stream" value={overviewQuery.data.callbacks.twilio_media_stream_url} />
              </CardContent>
            </Card>
          </div>

          <div className="grid gap-4 xl:grid-cols-2">
            <CredentialEditorCard
              title="SendGrid"
              description="Store workspace email credentials and default sender metadata."
              integration={sendgrid}
              configLabel="Default from email"
              configPlaceholder="ops@example.com"
              form={sendgridForm}
              onFormChange={setSendgridForm}
              onSubmit={() => {
                setFeedback(null)
                upsertCredential.mutate({
                  provider: "sendgrid",
                  channel: "email",
                  apiKey: sendgridForm.apiKey,
                  apiSecret: sendgridForm.apiSecret,
                  config: sendgridForm.configValue ? { from_email: sendgridForm.configValue } : {},
                })
              }}
              submitLabel="Save SendGrid"
              isSaving={upsertCredential.isPending}
            />
            <CredentialEditorCard
              title="Twilio Voice"
              description="Store workspace Twilio credentials and calling number."
              integration={twilio}
              configLabel="Phone number"
              configPlaceholder="+15551234567"
              form={twilioForm}
              onFormChange={setTwilioForm}
              onSubmit={() => {
                setFeedback(null)
                upsertCredential.mutate({
                  provider: "twilio",
                  channel: "voice",
                  apiKey: twilioForm.apiKey,
                  apiSecret: twilioForm.apiSecret,
                  config: twilioForm.configValue ? { phone_number: twilioForm.configValue } : {},
                })
              }}
              submitLabel="Save Twilio"
              isSaving={upsertCredential.isPending}
            />
          </div>

          <Card>
            <CardHeader>
              <CardTitle>Runtime services</CardTitle>
              <CardDescription>
                Save workspace overrides for Deepgram, Groq, and team notifications. Leave a field blank to keep the current value.
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="grid gap-4 md:grid-cols-3">
                {[deepgram, groq, teamNotifications].filter(Boolean).map((integration) => (
                  <div key={integration?.key} className="rounded-lg border p-4">
                    <div className="flex items-center justify-between gap-3">
                      <div>
                        <h3 className="font-medium">{integration?.label}</h3>
                        <p className="text-xs text-muted-foreground">Source: {integration?.source}</p>
                      </div>
                      <StatusBadge ready={integration?.configured ?? false} />
                    </div>
                    {integration && Object.entries(integration.config).length > 0 && (
                      <dl className="mt-3 space-y-2 text-sm text-muted-foreground">
                        {Object.entries(integration.config).map(([configKey, configValue]) => (
                          <div key={configKey} className="flex items-start justify-between gap-3">
                            <dt className="font-medium text-foreground">{formatLabel(configKey)}</dt>
                            <dd className="text-right break-all">{configValue}</dd>
                          </div>
                        ))}
                      </dl>
                    )}
                    {integration?.note && (
                      <p className="mt-3 text-sm text-muted-foreground">{integration.note}</p>
                    )}
                  </div>
                ))}
              </div>

              <div className="grid gap-4 md:grid-cols-3">
                <div className="grid gap-2">
                  <Label htmlFor="runtime-deepgram">Deepgram API key</Label>
                  <Input
                    id="runtime-deepgram"
                    type="password"
                    value={runtimeForm.deepgramApiKey}
                    onChange={(event) => setRuntimeForm({ ...runtimeForm, deepgramApiKey: event.target.value })}
                    placeholder="Enter workspace Deepgram key"
                  />
                </div>
                <div className="grid gap-2">
                  <Label htmlFor="runtime-groq">Groq API key</Label>
                  <Input
                    id="runtime-groq"
                    type="password"
                    value={runtimeForm.groqApiKey}
                    onChange={(event) => setRuntimeForm({ ...runtimeForm, groqApiKey: event.target.value })}
                    placeholder="Enter workspace Groq key"
                  />
                </div>
                <div className="grid gap-2">
                  <Label htmlFor="runtime-team-email">Team notification email</Label>
                  <Input
                    id="runtime-team-email"
                    type="email"
                    value={runtimeForm.teamNotificationEmail}
                    onChange={(event) => setRuntimeForm({ ...runtimeForm, teamNotificationEmail: event.target.value })}
                    placeholder="ops@example.com"
                  />
                </div>
              </div>

              <Button
                type="button"
                onClick={() => {
                  setFeedback(null)
                  upsertRuntimeConfig.mutate()
                }}
                disabled={upsertRuntimeConfig.isPending}
              >
                {upsertRuntimeConfig.isPending ? <Loader2 className="mr-2 size-4 animate-spin" /> : null}
                Save runtime services
              </Button>
            </CardContent>
          </Card>
        </>
      )}
    </div>
  )
}

function SetupStatusCard(props: {
  title: string
  description: string
  items: Array<{ label: string; ready: boolean; detail?: string }>
}) {
  return (
    <Card>
      <CardHeader>
        <CardTitle>{props.title}</CardTitle>
        <CardDescription>{props.description}</CardDescription>
      </CardHeader>
      <CardContent className="space-y-3">
        {props.items.map((item) => (
          <div key={item.label} className="rounded-md border p-3">
            <div className="flex items-center justify-between gap-3">
              <span className="font-medium">{item.label}</span>
              <StatusBadge ready={item.ready} />
            </div>
            {item.detail && <p className="mt-2 text-sm text-muted-foreground">{item.detail}</p>}
          </div>
        ))}
      </CardContent>
    </Card>
  )
}

function CredentialEditorCard(props: {
  title: string
  description: string
  integration?: SetupIntegration
  configLabel: string
  configPlaceholder: string
  form: CredentialFormState
  onFormChange: (value: CredentialFormState) => void
  onSubmit: () => void
  submitLabel: string
  isSaving: boolean
}) {
  const currentConfigValue = Object.values(props.integration?.config ?? {})[0] ?? ""
  const isConfigured = props.integration?.configured ?? false

  return (
    <Card>
      <CardHeader>
        <div className="flex items-center justify-between gap-3">
          <div>
            <CardTitle>{props.title}</CardTitle>
            <CardDescription>{props.description}</CardDescription>
          </div>
          <StatusBadge ready={isConfigured} />
        </div>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="rounded-md border p-3 text-sm">
          <div className="flex items-center justify-between gap-3">
            <span className="font-medium">Current source</span>
            <Badge variant="outline">{props.integration?.source ?? "missing"}</Badge>
          </div>
          {currentConfigValue && (
            <p className="mt-2 text-muted-foreground">
              Current {props.configLabel.toLowerCase()}: {currentConfigValue}
            </p>
          )}
          {props.integration?.note && (
            <p className="mt-2 text-muted-foreground">{props.integration.note}</p>
          )}
        </div>

        <div className="grid gap-2">
          <Label htmlFor={`${props.title}-api-key`}>API key / account SID</Label>
          <Input
            id={`${props.title}-api-key`}
            value={props.form.apiKey}
            onChange={(event) => props.onFormChange({ ...props.form, apiKey: event.target.value })}
            placeholder="Enter the primary credential"
          />
        </div>

        <div className="grid gap-2">
          <Label htmlFor={`${props.title}-api-secret`}>Secret / auth token</Label>
          <Input
            id={`${props.title}-api-secret`}
            type="password"
            value={props.form.apiSecret}
            onChange={(event) => props.onFormChange({ ...props.form, apiSecret: event.target.value })}
            placeholder="Optional secondary secret"
          />
        </div>

        <div className="grid gap-2">
          <Label htmlFor={`${props.title}-config`}>{props.configLabel}</Label>
          <Input
            id={`${props.title}-config`}
            value={props.form.configValue}
            onChange={(event) => props.onFormChange({ ...props.form, configValue: event.target.value })}
            placeholder={props.configPlaceholder}
          />
        </div>

        <Button
          type="button"
          onClick={props.onSubmit}
          disabled={!props.form.apiKey.trim() || props.isSaving}
        >
          {props.isSaving ? <Loader2 className="mr-2 size-4 animate-spin" /> : null}
          {props.submitLabel}
        </Button>
      </CardContent>
    </Card>
  )
}

function StatusBadge({ ready }: { ready: boolean }) {
  if (ready) {
    return (
      <Badge className="gap-1">
        <CheckCircle2 className="size-3.5" />
        Ready
      </Badge>
    )
  }

  return (
    <Badge variant="secondary" className="gap-1">
      <TriangleAlert className="size-3.5" />
      Needs setup
    </Badge>
  )
}

function UrlRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-md border p-3">
      <p className="font-medium">{label}</p>
      <p className="mt-1 break-all text-muted-foreground">{value}</p>
    </div>
  )
}

function formatLabel(value: string) {
  return value
    .split("_")
    .join(" ")
    .replace(/\b\w/g, (character: string) => character.toUpperCase())
}

function buildWorkerDetail(worker: SetupWorkerReadiness) {
  const parts = [`Status: ${worker.status}`]
  if (worker.last_seen_at) {
    parts.push(`Last seen: ${formatDateTime(worker.last_seen_at)}`)
  }
  if (worker.missing.length > 0) {
    parts.push(`Missing: ${worker.missing.join(", ")}`)
  }
  if (worker.last_error_message) {
    parts.push(`Error: ${worker.last_error_message}`)
  }
  if (worker.running && worker.missing.length === 0 && !worker.last_error_message) {
    parts.push("Heartbeat active")
  }
  return parts.join(" | ")
}

function formatDateTime(value: string) {
  return new Date(value).toLocaleString()
}
