type RequestOptions = {
  method?: "GET" | "POST" | "PUT" | "PATCH" | "DELETE"
  body?: unknown
  formData?: FormData
  idempotent?: boolean
  workspaceId?: string
}

type ApiErrorPayload = {
  detail?: string | { error?: { message?: string } }
}

export type ProviderCapability =
  | "email"
  | "sms"
  | "voice"
  | "stt"
  | "tts"
  | "llm"

export type ProviderOption = {
  provider: string
  label: string
  requires_creds: boolean
  free_tier?: string | null
  local: boolean
}

export type CapabilityOptions = {
  capability: ProviderCapability
  providers: ProviderOption[]
}

export type ProviderCatalogPublic = {
  data: CapabilityOptions[]
}

export type ProviderSelection = {
  id: string
  workspace_id: string
  capability: ProviderCapability
  provider: string
  is_active: boolean
}

export type ProviderSelectionsPublic = {
  data: ProviderSelection[]
  count: number
}

export type SetupIntegration = {
  key: string
  label: string
  configured: boolean
  source: string
  editable: boolean
  has_secret: boolean
  config: Record<string, string>
  note?: string | null
  capability?: ProviderCapability | null
  provider?: string | null
  provider_label?: string | null
  requires_creds?: boolean | null
  local?: boolean | null
}

export type SetupWorkerReadiness = {
  key: string
  label: string
  ready: boolean
  running: boolean
  status: string
  last_seen_at?: string | null
  last_error_message?: string | null
  missing: string[]
}

export type SetupOverview = {
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

const getApiBase = () => {
  const base = import.meta.env.VITE_API_URL || ""
  return base.endsWith("/") ? base.slice(0, -1) : base
}

const getAuthToken = () => localStorage.getItem("access_token") || ""

export const getWorkspaceId = () =>
  localStorage.getItem("workspace_id") || "default"

const isAuthFailure = (status: number, message: string) => {
  return status === 401 || (status === 404 && message === "User not found")
}

const redirectToLogin = () => {
  localStorage.removeItem("access_token")
  if (window.location.pathname !== "/login") {
    window.location.href = "/login"
  }
}

const parseError = async (response: Response) => {
  let payload: ApiErrorPayload | null = null
  try {
    payload = (await response.json()) as ApiErrorPayload
  } catch {
    payload = null
  }

  if (typeof payload?.detail === "string") {
    return payload.detail
  }

  const semanticMessage =
    payload?.detail && typeof payload.detail !== "string"
      ? payload.detail.error?.message
      : undefined

  return semanticMessage || `Request failed with status ${response.status}`
}

export async function signalloopRequest<T>(
  path: string,
  options?: RequestOptions,
): Promise<T> {
  const headers = new Headers()
  headers.set("Authorization", `Bearer ${getAuthToken()}`)
  headers.set("X-Workspace-Id", options?.workspaceId || getWorkspaceId())

  if (options?.idempotent) {
    headers.set("Idempotency-Key", crypto.randomUUID())
  }

  let body: BodyInit | undefined
  if (options?.formData) {
    body = options.formData
  } else if (options?.body !== undefined) {
    headers.set("Content-Type", "application/json")
    body = JSON.stringify(options.body)
  }

  const response = await fetch(`${getApiBase()}${path}`, {
    method: options?.method || "GET",
    headers,
    body,
  })

  if (!response.ok) {
    const message = await parseError(response)
    if (isAuthFailure(response.status, message)) {
      redirectToLogin()
    }
    throw new Error(message)
  }

  if (response.status === 204) {
    return undefined as T
  }

  return (await response.json()) as T
}

export function getProviderOptions(workspaceId = getWorkspaceId()) {
  return signalloopRequest<ProviderCatalogPublic>(
    `/api/v1/workspaces/${workspaceId}/provider-options`,
    { workspaceId },
  )
}

export function getProviderSelections(workspaceId = getWorkspaceId()) {
  return signalloopRequest<ProviderSelectionsPublic>(
    `/api/v1/workspaces/${workspaceId}/provider-selection`,
    { workspaceId },
  )
}

export function getSetupOverview(workspaceId = getWorkspaceId()) {
  return signalloopRequest<SetupOverview>("/api/v1/utils/setup-overview/", {
    workspaceId,
  })
}

export function updateProviderSelection(
  input: {
    capability: ProviderCapability
    provider: string
  },
  workspaceId = getWorkspaceId(),
) {
  return signalloopRequest<ProviderSelection>(
    `/api/v1/workspaces/${workspaceId}/provider-selection`,
    {
      method: "PUT",
      body: input,
      workspaceId,
    },
  )
}
