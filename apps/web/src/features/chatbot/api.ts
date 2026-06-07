import { engagehubRequest, getWorkspaceId } from "@/lib/engagehub-api"
import {
  demoCreateChatbotChannel,
  demoCreateKnowledgeSource,
  demoDeleteKnowledgeSource,
  demoGetChatbotAnalytics,
  demoExportChatbotThreads,
  demoGetChatbotConfig,
  demoGetChatbotThread,
  demoListChatbotDeadLetters,
  demoListChatbotChannels,
  demoListChatbotOptOuts,
  demoListChatbotThreads,
  demoListKnowledgeSources,
  demoReindexAllKnowledgeSources,
  demoReindexKnowledgeSource,
  demoRemoveChatbotOptOut,
  demoReopenChatbotThread,
  demoReplyToChatbotThread,
  demoRetryChatbotDeadLetter,
  demoResolveChatbotThread,
  demoStreamChatbotInboxEvents,
  demoTestChatbotQuestion,
  demoToggleChatbotChannel,
  demoUpdateChatbotChannel,
  demoUpdateChatbotConfig,
  demoUploadKnowledgeDocument,
  isChatbotDemoMode,
} from "@/features/chatbot/demo"

export type ChatbotChannelType =
  | "facebook_messenger"
  | "whatsapp_business"
  | "telegram"
  | "linkedin_redirect"

export type ChatbotChannelStatus =
  | "draft"
  | "pending_approval"
  | "connected"
  | "error"
  | "disabled"

export type ChatbotChannel = {
  id: string
  workspace_id: string
  channel_type: ChatbotChannelType
  display_name: string
  status: ChatbotChannelStatus
  is_active: boolean
  has_credential: boolean
  config_json: Record<string, unknown>
  last_verified_at?: string | null
  created_at: string
  updated_at: string
}

export type ChatbotChannelsResponse = {
  data: ChatbotChannel[]
  count: number
}

export type ChatbotChannelInput = {
  channel_type: ChatbotChannelType
  display_name: string
  credentials: {
    api_key: string
    api_secret?: string | null
    webhook_secret?: string | null
  }
  config_json: Record<string, unknown>
  is_active: boolean
}

export type ChatbotChannelUpdateInput = Partial<Omit<ChatbotChannelInput, "channel_type">>

const channelPath = (workspaceId = getWorkspaceId()) => ({
  workspaceId,
  path: "/api/v1/chatbot/channels",
})

export function listChatbotChannels(workspaceId = getWorkspaceId()) {
  if (isChatbotDemoMode()) return demoListChatbotChannels()
  return engagehubRequest<ChatbotChannelsResponse>(channelPath(workspaceId).path, { workspaceId })
}

export function createChatbotChannel(input: ChatbotChannelInput, workspaceId = getWorkspaceId()) {
  if (isChatbotDemoMode()) return demoCreateChatbotChannel(input)
  return engagehubRequest<ChatbotChannel>(channelPath(workspaceId).path, {
    method: "POST",
    body: input,
    workspaceId,
  })
}

export function updateChatbotChannel(
  channelId: string,
  input: ChatbotChannelUpdateInput,
  workspaceId = getWorkspaceId(),
) {
  if (isChatbotDemoMode()) return demoUpdateChatbotChannel(channelId, input)
  return engagehubRequest<ChatbotChannel>(`${channelPath(workspaceId).path}/${channelId}`, {
    method: "PUT",
    body: input,
    workspaceId,
  })
}

export function toggleChatbotChannel(
  channelId: string,
  isActive: boolean,
  workspaceId = getWorkspaceId(),
) {
  if (isChatbotDemoMode()) return demoToggleChatbotChannel(channelId, isActive)
  return engagehubRequest<ChatbotChannel>(`${channelPath(workspaceId).path}/${channelId}/toggle`, {
    method: "PATCH",
    body: { is_active: isActive },
    workspaceId,
  })
}

export type ChatbotKnowledgeSourceType =
  | "website"
  | "document"
  | "faq"
  | "manual_text"
  | "qa_pair"

export type ChatbotKnowledgeStatus =
  | "pending"
  | "indexing"
  | "ready"
  | "failed"
  | "stale"
  | "archived"

export type ChatbotKnowledgeSource = {
  id: string
  workspace_id: string
  source_type: ChatbotKnowledgeSourceType
  title: string
  source_uri?: string | null
  status: ChatbotKnowledgeStatus
  index_version: number
  chunk_count: number
  error_message?: string | null
  progress: number
  created_at: string
  updated_at: string
  indexed_at?: string | null
}

export type ChatbotKnowledgeSourcesResponse = {
  data: ChatbotKnowledgeSource[]
  count: number
}

export type ChatbotKnowledgeSourceInput = {
  source_type: ChatbotKnowledgeSourceType
  title: string
  source_uri?: string | null
  content?: string | null
  question?: string | null
  answer?: string | null
  crawl_depth?: number
  max_pages?: number
}

export type ChatbotReindexResponse = {
  job_id: string
  queued: number
  workspace_id: string
  status: string
}

export type ChatbotAnalytics = {
  workspace_id: string
  date_from: string
  date_to: string
  updated_at: string
  totals: {
    conversations: number
    containment_rate: number
    leads_captured: number
    escalations: number
    bot_messages: number
    opt_outs: number
  }
  timeseries: Array<{
    date: string
    conversations: number
    bot_messages: number
    leads_captured: number
    escalations: number
    opt_outs: number
  }>
  channel_breakdown: Array<{
    channel_type: ChatbotChannelType
    bot_resolved: number
    escalated: number
    lead_captured: number
    opted_out: number
    conversations: number
  }>
}

export type ChatbotAnalyticsRange = {
  from?: string
  to?: string
}

export function getChatbotAnalytics(range: ChatbotAnalyticsRange = {}, workspaceId = getWorkspaceId()) {
  if (isChatbotDemoMode()) return demoGetChatbotAnalytics(range)
  const params = new URLSearchParams()
  if (range.from) params.set("from", range.from)
  if (range.to) params.set("to", range.to)
  const query = params.toString()
  return engagehubRequest<ChatbotAnalytics>(`/api/v1/chatbot/analytics${query ? `?${query}` : ""}`, { workspaceId })
}

export type ChatbotTestBotSource = {
  source_id: string
  source_title: string
  chunk_id: string
  excerpt: string
  score: number
}

export type ChatbotTestBotResponse = {
  answer: string
  ai_disclosure: string
  sources: ChatbotTestBotSource[]
  no_kb: boolean
}

const knowledgePath = "/api/v1/chatbot/knowledge-sources"

export function listKnowledgeSources(workspaceId = getWorkspaceId()) {
  if (isChatbotDemoMode()) return demoListKnowledgeSources()
  return engagehubRequest<ChatbotKnowledgeSourcesResponse>(knowledgePath, { workspaceId })
}

export function createKnowledgeSource(input: ChatbotKnowledgeSourceInput, workspaceId = getWorkspaceId()) {
  if (isChatbotDemoMode()) return demoCreateKnowledgeSource(input)
  return engagehubRequest<ChatbotKnowledgeSource>(knowledgePath, {
    method: "POST",
    body: input,
    workspaceId,
  })
}

export function uploadKnowledgeDocument(file: File, workspaceId = getWorkspaceId()) {
  if (isChatbotDemoMode()) return demoUploadKnowledgeDocument(file)
  const formData = new FormData()
  formData.append("file", file)
  return engagehubRequest<ChatbotKnowledgeSource>(`${knowledgePath}/documents`, {
    method: "POST",
    formData,
    workspaceId,
  })
}

export function deleteKnowledgeSource(sourceId: string, workspaceId = getWorkspaceId()) {
  if (isChatbotDemoMode()) return demoDeleteKnowledgeSource(sourceId)
  return engagehubRequest<void>(`${knowledgePath}/${sourceId}`, {
    method: "DELETE",
    workspaceId,
  })
}

export function reindexKnowledgeSource(sourceId: string, workspaceId = getWorkspaceId()) {
  if (isChatbotDemoMode()) return demoReindexKnowledgeSource(sourceId)
  return engagehubRequest<ChatbotReindexResponse>(`${knowledgePath}/${sourceId}/reindex`, {
    method: "POST",
    workspaceId,
  })
}

export function reindexAllKnowledgeSources(workspaceId = getWorkspaceId()) {
  if (isChatbotDemoMode()) return demoReindexAllKnowledgeSources()
  return engagehubRequest<ChatbotReindexResponse>(`${knowledgePath}/reindex`, {
    method: "POST",
    body: {},
    workspaceId,
  })
}

export function testChatbotQuestion(question: string, workspaceId = getWorkspaceId()) {
  if (isChatbotDemoMode()) return demoTestChatbotQuestion(question)
  return engagehubRequest<ChatbotTestBotResponse>("/api/v1/chatbot/test-bot", {
    method: "POST",
    body: { question },
    workspaceId,
  })
}

export type ChatbotConversationStatus =
  | "open"
  | "escalated"
  | "agent_active"
  | "resolved"
  | "bot_paused"

export type ChatbotMessageSender = "visitor" | "bot" | "agent" | "system"

export type ChatbotLeadDetails = {
  contact_id?: string | null
  name?: string | null
  email?: string | null
  phone?: string | null
  source_channel?: string | null
  tags: string[]
  intents: string[]
}

export type ChatbotThreadSummary = {
  id: string
  workspace_id: string
  channel_type: ChatbotChannelType
  visitor_id: string
  status: ChatbotConversationStatus
  outcome?: string | null
  preview?: string | null
  last_message_at?: string | null
  customer_last_message_at?: string | null
  is_whatsapp_window_open: boolean
  is_opted_out: boolean
  escalation_reason?: string | null
  lead?: ChatbotLeadDetails | null
}

export type ChatbotThreadMessage = {
  id: string
  direction: "inbound" | "outbound"
  sender: ChatbotMessageSender
  message_type: string
  content?: string | null
  bot_confidence?: number | null
  metadata_json: Record<string, unknown>
  created_at: string
  delivered_at?: string | null
}

export type ChatbotThreadDetail = ChatbotThreadSummary & {
  messages: ChatbotThreadMessage[]
}

export type ChatbotThreadsResponse = {
  data: ChatbotThreadSummary[]
  count: number
  next_cursor?: string | null
}

export type ChatbotThreadFilters = {
  channel_type?: ChatbotChannelType | "all"
  status?: ChatbotConversationStatus | "all"
  cursor?: string | null
}

const inboxPath = "/api/v1/chatbot/inbox"

const getApiBase = () => {
  const base = import.meta.env.VITE_API_URL || ""
  return base.endsWith("/") ? base.slice(0, -1) : base
}

const chatbotHeaders = (workspaceId = getWorkspaceId()) => {
  const headers = new Headers()
  headers.set("Authorization", `Bearer ${localStorage.getItem("access_token") || ""}`)
  headers.set("X-Workspace-Id", workspaceId)
  return headers
}

const parseChatbotFetchError = async (response: Response) => {
  try {
    const payload = await response.json()
    if (typeof payload?.detail === "string") return payload.detail
    if (payload?.detail?.error?.message) return payload.detail.error.message
  } catch {
    // Fall through to status-based message.
  }
  return `Request failed with status ${response.status}`
}

export function listChatbotThreads(filters: ChatbotThreadFilters = {}, workspaceId = getWorkspaceId()) {
  if (isChatbotDemoMode()) return demoListChatbotThreads(filters)
  const params = new URLSearchParams()
  if (filters.channel_type && filters.channel_type !== "all") params.set("channel_type", filters.channel_type)
  if (filters.status && filters.status !== "all") params.set("status", filters.status)
  if (filters.cursor) params.set("cursor", filters.cursor)
  const query = params.toString()
  return engagehubRequest<ChatbotThreadsResponse>(`${inboxPath}/threads${query ? `?${query}` : ""}`, { workspaceId })
}

export function getChatbotThread(threadId: string, workspaceId = getWorkspaceId()) {
  if (isChatbotDemoMode()) return demoGetChatbotThread(threadId)
  return engagehubRequest<ChatbotThreadDetail>(`${inboxPath}/threads/${threadId}`, { workspaceId })
}

export function replyToChatbotThread(threadId: string, message: string, workspaceId = getWorkspaceId()) {
  if (isChatbotDemoMode()) return demoReplyToChatbotThread(threadId, message)
  return engagehubRequest<{ thread: ChatbotThreadDetail }>(`${inboxPath}/threads/${threadId}/reply`, {
    method: "POST",
    body: { message },
    workspaceId,
  })
}

export function resolveChatbotThread(threadId: string, workspaceId = getWorkspaceId()) {
  if (isChatbotDemoMode()) return demoResolveChatbotThread(threadId)
  return engagehubRequest<{ thread: ChatbotThreadDetail }>(`${inboxPath}/threads/${threadId}/resolve`, {
    method: "PATCH",
    workspaceId,
  })
}

export function reopenChatbotThread(threadId: string, workspaceId = getWorkspaceId()) {
  if (isChatbotDemoMode()) return demoReopenChatbotThread(threadId)
  return engagehubRequest<{ thread: ChatbotThreadDetail }>(`${inboxPath}/threads/${threadId}/reopen`, {
    method: "PATCH",
    workspaceId,
  })
}

export type ChatbotExportFormat = "csv" | "json"

export async function exportChatbotThreads(
  format: ChatbotExportFormat,
  filters: ChatbotThreadFilters = {},
  workspaceId = getWorkspaceId(),
) {
  if (isChatbotDemoMode()) return demoExportChatbotThreads(format, filters)
  const params = new URLSearchParams({ format })
  if (filters.channel_type && filters.channel_type !== "all") params.set("channel_type", filters.channel_type)

  const response = await fetch(`${getApiBase()}${inboxPath}/threads/export?${params.toString()}`, {
    headers: chatbotHeaders(workspaceId),
  })
  if (!response.ok) {
    throw new Error(await parseChatbotFetchError(response))
  }

  const disposition = response.headers.get("Content-Disposition") || ""
  const filename = disposition.match(/filename=([^;]+)/)?.[1]?.replace(/"/g, "") || `chatbot-conversations.${format}`
  return { blob: await response.blob(), filename }
}

type ChatbotInboxStreamOptions = {
  signal: AbortSignal
  onInbox: () => void
  onOpen: () => void
  workspaceId?: string
}

export async function streamChatbotInboxEvents({
  signal,
  onInbox,
  onOpen,
  workspaceId = getWorkspaceId(),
}: ChatbotInboxStreamOptions) {
  if (isChatbotDemoMode()) {
    return demoStreamChatbotInboxEvents({ signal, onInbox, onOpen })
  }
  const response = await fetch(`${getApiBase()}${inboxPath}/events`, {
    headers: chatbotHeaders(workspaceId),
    signal,
  })
  if (!response.ok) {
    throw new Error(await parseChatbotFetchError(response))
  }
  onOpen()
  if (!response.body) return

  const reader = response.body.getReader()
  const decoder = new TextDecoder()
  let buffer = ""

  while (true) {
    const { done, value } = await reader.read()
    if (done) break
    buffer += decoder.decode(value, { stream: true })
    const frames = buffer.split("\n\n")
    buffer = frames.pop() || ""
    for (const frame of frames) {
      if (frame.includes("event: inbox")) {
        onInbox()
      }
    }
  }
}

export type ChatbotBusinessHoursConfig = {
  enabled: boolean
  timezone: string
  days: number[]
  start: string
  end: string
}

export type ChatbotLeadCaptureConfig = {
  enabled: boolean
  min_turns: number
  intent_keywords: string[]
  privacy_notice_text?: string | null
  privacy_policy_url?: string | null
  re_opt_in_invitation_enabled: boolean
  confidence_threshold: number
}

export type ChatbotConfig = {
  workspace_id: string
  bot_name: string
  persona?: string | null
  greeting_message?: string | null
  escalation_message?: string | null
  out_of_hours_message?: string | null
  ai_disclosure: string
  token_cap_per_session: number
  retention_days: number
  business_hours: ChatbotBusinessHoursConfig
  lead_capture: ChatbotLeadCaptureConfig
  reindex_schedule_time: string
  channel_overrides: ChatbotChannel[]
  updated_at: string
}

export type ChatbotConfigUpdate = Partial<Omit<ChatbotConfig, "workspace_id" | "channel_overrides" | "updated_at">>

export function getChatbotConfig(workspaceId = getWorkspaceId()) {
  if (isChatbotDemoMode()) return demoGetChatbotConfig()
  return engagehubRequest<ChatbotConfig>("/api/v1/chatbot/config", { workspaceId })
}

export function updateChatbotConfig(input: ChatbotConfigUpdate, workspaceId = getWorkspaceId()) {
  if (isChatbotDemoMode()) return demoUpdateChatbotConfig(input)
  return engagehubRequest<ChatbotConfig>("/api/v1/chatbot/config", {
    method: "PUT",
    body: input,
    workspaceId,
  })
}

export type ChatbotOptOut = {
  id: string
  workspace_id: string
  channel_type: ChatbotChannelType
  visitor_id: string
  contact_id?: string | null
  reason?: string | null
  actor: string
  created_at: string
  reopt_in_invited_at?: string | null
}

export type ChatbotOptOutsResponse = {
  data: ChatbotOptOut[]
  count: number
}

export function listChatbotOptOuts(workspaceId = getWorkspaceId()) {
  if (isChatbotDemoMode()) return demoListChatbotOptOuts()
  return engagehubRequest<ChatbotOptOutsResponse>("/api/v1/chatbot/opt-outs", { workspaceId })
}

export function removeChatbotOptOut(optOutId: string, workspaceId = getWorkspaceId()) {
  if (isChatbotDemoMode()) return demoRemoveChatbotOptOut(optOutId)
  return engagehubRequest<{ id: string; removed: boolean }>(`/api/v1/chatbot/opt-outs/${optOutId}`, {
    method: "DELETE",
    workspaceId,
  })
}

export type ChatbotDeadLetter = {
  id: string
  workspace_id: string
  channel_type: ChatbotChannelType
  provider_message_id: string
  payload: Record<string, unknown>
  attempt_count: number
  last_error: string
  failed_at: string
  status: string
}

export type ChatbotDeadLettersResponse = {
  data: ChatbotDeadLetter[]
  count: number
}

export function listChatbotDeadLetters(workspaceId = getWorkspaceId()) {
  if (isChatbotDemoMode()) return demoListChatbotDeadLetters()
  return engagehubRequest<ChatbotDeadLettersResponse>("/api/v1/chatbot/dead-letters", { workspaceId })
}

export function retryChatbotDeadLetter(deadLetterId: string, workspaceId = getWorkspaceId()) {
  if (isChatbotDemoMode()) return demoRetryChatbotDeadLetter(deadLetterId)
  return engagehubRequest<{ id: string; requeued: boolean; inbound_queue_key: string }>(
    `/api/v1/chatbot/dead-letters/${deadLetterId}/retry`,
    { method: "POST", workspaceId },
  )
}
