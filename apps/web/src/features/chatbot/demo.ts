import type {
  ChatbotChannel,
  ChatbotChannelInput,
  ChatbotChannelUpdateInput,
  ChatbotAnalytics,
  ChatbotAnalyticsRange,
  ChatbotChannelsResponse,
  ChatbotConfig,
  ChatbotConfigUpdate,
  ChatbotDeadLetter,
  ChatbotDeadLettersResponse,
  ChatbotExportFormat,
  ChatbotKnowledgeSource,
  ChatbotKnowledgeSourceInput,
  ChatbotKnowledgeSourcesResponse,
  ChatbotOptOut,
  ChatbotOptOutsResponse,
  ChatbotReindexResponse,
  ChatbotTestBotResponse,
  ChatbotThreadDetail,
  ChatbotThreadFilters,
  ChatbotThreadMessage,
  ChatbotThreadSummary,
  ChatbotThreadsResponse,
} from "@/features/chatbot/api"

const DEMO_WORKSPACE_ID = "demo-workspace"
const DEMO_MODE_KEY = "chatbot_demo_mode"

const iso = (offsetMinutes = 0) => new Date(Date.now() + offsetMinutes * 60_000).toISOString()

const delay = async () => {
  await new Promise((resolve) => window.setTimeout(resolve, 180))
}

export function isChatbotDemoMode() {
  if (import.meta.env.VITE_CHATBOT_DEMO === "1") return true
  if (typeof window === "undefined") return false
  const params = new URLSearchParams(window.location.search)
  if (params.get("chatbotDemo") === "1") {
    localStorage.setItem(DEMO_MODE_KEY, "true")
    return true
  }
  return localStorage.getItem(DEMO_MODE_KEY) === "true"
}

let demoChannels: ChatbotChannel[] = [
  {
    id: "demo-channel-wa",
    workspace_id: DEMO_WORKSPACE_ID,
    channel_type: "whatsapp_business",
    display_name: "Main WhatsApp number",
    status: "connected",
    is_active: true,
    has_credential: true,
    config_json: { phone_number_id: "15551234567", verify_token: "configured", webhook_secret_present: true },
    readiness: {
      ready: true,
      status: "ready",
      missing: [],
      webhook_url_path: "/api/v1/chatbot/webhooks/demo-channel-wa",
    },
    last_verified_at: iso(-120),
    created_at: iso(-7200),
    updated_at: iso(-120),
  },
  {
    id: "demo-channel-fb",
    workspace_id: DEMO_WORKSPACE_ID,
    channel_type: "facebook_messenger",
    display_name: "SignalLoop Facebook Page",
    status: "connected",
    is_active: true,
    has_credential: true,
    config_json: { page_id: "108812345678901", verify_token: "configured", webhook_secret_present: true },
    readiness: {
      ready: true,
      status: "ready",
      missing: [],
      webhook_url_path: "/api/v1/chatbot/webhooks/demo-channel-fb",
    },
    last_verified_at: iso(-180),
    created_at: iso(-7000),
    updated_at: iso(-180),
  },
  {
    id: "demo-channel-tg",
    workspace_id: DEMO_WORKSPACE_ID,
    channel_type: "telegram",
    display_name: "Telegram qualification bot",
    status: "pending_approval",
    is_active: false,
    has_credential: true,
    config_json: { bot_username: "signalloop_demo_bot" },
    readiness: {
      ready: false,
      status: "needs_webhook",
      missing: ["webhook secret", "activation"],
      webhook_url_path: "/api/v1/chatbot/webhooks/demo-channel-tg",
    },
    last_verified_at: null,
    created_at: iso(-5000),
    updated_at: iso(-45),
  },
]

let demoKnowledgeSources: ChatbotKnowledgeSource[] = [
  {
    id: "demo-source-pricing",
    workspace_id: DEMO_WORKSPACE_ID,
    source_type: "faq",
    title: "Pricing and demo FAQ",
    source_uri: null,
    status: "ready",
    index_version: 3,
    chunk_count: 18,
    error_message: null,
    progress: 100,
    created_at: iso(-4800),
    updated_at: iso(-90),
    indexed_at: iso(-90),
  },
  {
    id: "demo-source-site",
    workspace_id: DEMO_WORKSPACE_ID,
    source_type: "website",
    title: "Public marketing site",
    source_uri: "https://example.com",
    status: "ready",
    index_version: 3,
    chunk_count: 42,
    error_message: null,
    progress: 100,
    created_at: iso(-4600),
    updated_at: iso(-180),
    indexed_at: iso(-180),
  },
  {
    id: "demo-source-onboarding",
    workspace_id: DEMO_WORKSPACE_ID,
    source_type: "document",
    title: "Sales onboarding playbook.pdf",
    source_uri: null,
    status: "indexing",
    index_version: 4,
    chunk_count: 11,
    error_message: null,
    progress: 64,
    created_at: iso(-800),
    updated_at: iso(-4),
    indexed_at: null,
  },
]

let demoConfig: ChatbotConfig = {
  workspace_id: DEMO_WORKSPACE_ID,
  bot_name: "SignalLoop Assistant",
  persona: "Concise, helpful sales assistant. Qualify fit, answer from approved knowledge, escalate when unsure.",
  greeting_message: "Hi, I am the SignalLoop AI assistant. How can I help?",
  escalation_message: "I do not have enough confidence to answer that. A teammate can help from here.",
  out_of_hours_message: "Our team is offline right now, but I can collect details for follow-up.",
  ai_disclosure: "AI assistant",
  token_cap_per_session: 4000,
  retention_days: 90,
  business_hours: {
    enabled: true,
    timezone: "America/New_York",
    days: [1, 2, 3, 4, 5],
    start: "09:00",
    end: "17:00",
  },
  lead_capture: {
    enabled: true,
    min_turns: 3,
    intent_keywords: ["demo", "pricing", "quote", "sales"],
    privacy_notice_text: "Before I collect your contact details, please confirm consent for follow-up.",
    privacy_policy_url: "https://example.com/privacy",
    re_opt_in_invitation_enabled: true,
    confidence_threshold: 0.35,
  },
  reindex_schedule_time: "02:00",
  channel_overrides: demoChannels,
  updated_at: iso(-30),
}

let demoOptOuts: ChatbotOptOut[] = [
  {
    id: "demo-optout-1",
    workspace_id: DEMO_WORKSPACE_ID,
    channel_type: "whatsapp_business",
    visitor_id: "15559876543",
    contact_id: null,
    reason: "STOP",
    actor: "visitor",
    created_at: iso(-220),
    reopt_in_invited_at: null,
  },
]

let demoDeadLetters: ChatbotDeadLetter[] = [
  {
    id: "demo-dead-letter-1",
    workspace_id: DEMO_WORKSPACE_ID,
    channel_type: "whatsapp_business",
    provider_message_id: "wamid.demo.failed",
    payload: {
      payload: {
        visitor_id: "15550111222",
        text: "Need pricing help",
      },
    },
    attempt_count: 3,
    last_error: "401 invalid token",
    failed_at: iso(-125),
    status: "dead_lettered",
  },
  {
    id: "demo-dead-letter-2",
    workspace_id: DEMO_WORKSPACE_ID,
    channel_type: "telegram",
    provider_message_id: "tg-demo-7718",
    payload: {
      payload: {
        visitor_id: "tg-7718",
        text: "Does the bot know clinic onboarding?",
      },
    },
    attempt_count: 3,
    last_error: "Index unavailable",
    failed_at: iso(-55),
    status: "dead_lettered",
  },
]

let demoThreads: ChatbotThreadDetail[] = [
  {
    id: "demo-thread-escalated",
    workspace_id: DEMO_WORKSPACE_ID,
    channel_type: "whatsapp_business",
    visitor_id: "15550199000",
    status: "escalated",
    outcome: null,
    preview: "Can someone help me compare pricing for three locations?",
    last_message_at: iso(-2),
    customer_last_message_at: iso(-2),
    is_whatsapp_window_open: true,
    is_opted_out: false,
    escalation_reason: "explicit_human_request",
    lead: {
      contact_id: "demo-contact-1",
      name: "Maya Singh",
      email: "maya@example.com",
      phone: "+1 555 019 9000",
      source_channel: "whatsapp_business",
      tags: ["chatbot-lead", "pricing"],
      intents: ["demo", "pricing"],
    },
    messages: [
      message("m1", "inbound", "visitor", "Hi, do you have pricing for three clinic locations?", -18),
      message("m2", "outbound", "bot", "AI assistant: I can help. Pricing depends on usage and channel mix.", -17, 0.82),
      message("m3", "inbound", "visitor", "Can someone help me compare pricing for three locations?", -2),
      message("m4", "outbound", "bot", "AI assistant: I will hand this to a teammate with the conversation context.", -1, 1),
    ],
  },
  {
    id: "demo-thread-open",
    workspace_id: DEMO_WORKSPACE_ID,
    channel_type: "facebook_messenger",
    visitor_id: "fb-88210",
    status: "open",
    outcome: null,
    preview: "Does SignalLoop support Telegram handoff?",
    last_message_at: iso(-14),
    customer_last_message_at: iso(-14),
    is_whatsapp_window_open: false,
    is_opted_out: false,
    escalation_reason: null,
    lead: null,
    messages: [
      message("m5", "inbound", "visitor", "Does SignalLoop support Telegram handoff?", -14),
      message("m6", "outbound", "bot", "AI assistant: Telegram can be connected as an optional channel in the MVP.", -13, 0.76),
    ],
  },
  {
    id: "demo-thread-resolved",
    workspace_id: DEMO_WORKSPACE_ID,
    channel_type: "telegram",
    visitor_id: "tg-44122",
    status: "resolved",
    outcome: "lead_captured",
    preview: "Thanks, that answers my question.",
    last_message_at: iso(-95),
    customer_last_message_at: iso(-95),
    is_whatsapp_window_open: false,
    is_opted_out: false,
    escalation_reason: null,
    lead: {
      contact_id: "demo-contact-2",
      name: "Jordan Lee",
      email: "jordan@example.com",
      phone: null,
      source_channel: "telegram",
      tags: ["chatbot-lead"],
      intents: ["demo"],
    },
    messages: [
      message("m7", "inbound", "visitor", "Can I book a demo?", -140),
      message("m8", "outbound", "bot", "AI assistant: Yes. Before collecting details, please confirm consent for follow-up.", -139, 1),
      message("m9", "inbound", "visitor", "Yes. Jordan Lee, jordan@example.com", -132),
      message("m10", "outbound", "agent", "Thanks Jordan. I sent you a booking link.", -100),
      message("m11", "inbound", "visitor", "Thanks, that answers my question.", -95),
    ],
  },
]

function message(
  id: string,
  direction: ChatbotThreadMessage["direction"],
  sender: ChatbotThreadMessage["sender"],
  content: string,
  offsetMinutes: number,
  confidence?: number,
): ChatbotThreadMessage {
  return {
    id,
    direction,
    sender,
    message_type: "text",
    content,
    bot_confidence: confidence,
    metadata_json: confidence === undefined ? {} : { delivery_status: "queued" },
    created_at: iso(offsetMinutes),
    delivered_at: direction === "outbound" ? iso(offsetMinutes + 1) : null,
  }
}

function summarize(thread: ChatbotThreadDetail): ChatbotThreadSummary {
  const { messages: _messages, ...summary } = thread
  return summary
}

function nextId(prefix: string) {
  return `${prefix}-${Math.random().toString(36).slice(2, 9)}`
}

function demoChannelReadiness(input: {
  id: string
  channel_type: ChatbotChannel["channel_type"]
  config_json: ChatbotChannel["config_json"]
  has_credential: boolean
  is_active: boolean
}): ChatbotChannel["readiness"] {
  const missing: string[] = []
  const requiredField =
    input.channel_type === "whatsapp_business"
      ? "phone_number_id"
      : input.channel_type === "facebook_messenger"
        ? "page_id"
        : input.channel_type === "telegram"
          ? "bot_username"
          : "redirect_url"

  if (!input.has_credential) missing.push("provider credential")
  if (!String(input.config_json[requiredField] || "").trim()) missing.push(requiredField)
  if (!input.config_json.webhook_secret_present) missing.push("webhook secret")
  if (
    (input.channel_type === "whatsapp_business" || input.channel_type === "facebook_messenger") &&
    !String(input.config_json.verify_token || "").trim()
  ) {
    missing.push("verify_token")
  }
  if (!input.is_active) missing.push("activation")

  const status = !input.has_credential
    ? "needs_credentials"
    : missing.includes("webhook secret") || missing.includes("verify_token")
      ? "needs_webhook"
      : missing.length === 1 && missing[0] === "activation"
        ? "needs_activation"
        : missing.length > 0
          ? "needs_provider_config"
          : "ready"

  return {
    ready: status === "ready",
    status,
    missing,
    webhook_url_path: `/api/v1/chatbot/webhooks/${input.id}`,
  }
}

export async function demoListChatbotChannels(): Promise<ChatbotChannelsResponse> {
  await delay()
  return { data: [...demoChannels], count: demoChannels.length }
}

export async function demoCreateChatbotChannel(input: ChatbotChannelInput): Promise<ChatbotChannel> {
  await delay()
  const existing = demoChannels.find((channel) => channel.channel_type === input.channel_type)
  const configJson = {
    ...input.config_json,
    ...(input.credentials.webhook_secret ? { webhook_secret_present: true } : {}),
  }
  const row: ChatbotChannel = {
    id: existing?.id || nextId("demo-channel"),
    workspace_id: DEMO_WORKSPACE_ID,
    channel_type: input.channel_type,
    display_name: input.display_name,
    status: input.is_active ? "connected" : "draft",
    is_active: input.is_active,
    has_credential: true,
    config_json: configJson,
    readiness: demoChannelReadiness({
      id: existing?.id || "pending",
      channel_type: input.channel_type,
      config_json: configJson,
      has_credential: true,
      is_active: input.is_active,
    }),
    last_verified_at: input.is_active ? iso() : null,
    created_at: existing?.created_at || iso(),
    updated_at: iso(),
  }
  row.readiness = demoChannelReadiness(row)
  demoChannels = existing
    ? demoChannels.map((channel) => (channel.id === existing.id ? row : channel))
    : [...demoChannels, row]
  demoConfig = { ...demoConfig, channel_overrides: demoChannels, updated_at: iso() }
  return row
}

export async function demoUpdateChatbotChannel(
  channelId: string,
  input: ChatbotChannelUpdateInput,
): Promise<ChatbotChannel> {
  await delay()
  const current = demoChannels.find((channel) => channel.id === channelId)
  if (!current) throw new Error("Demo channel not found")
  const configJson = {
    ...(input.config_json ?? current.config_json),
    ...(input.credentials?.webhook_secret ? { webhook_secret_present: true } : {}),
  }
  const updated: ChatbotChannel = {
    ...current,
    display_name: input.display_name ?? current.display_name,
    is_active: input.is_active ?? current.is_active,
    status: input.is_active === false ? "disabled" : current.status,
    has_credential: current.has_credential || Boolean(input.credentials?.api_key),
    config_json: configJson,
    readiness: current.readiness,
    updated_at: iso(),
  }
  updated.readiness = demoChannelReadiness(updated)
  demoChannels = demoChannels.map((channel) => (channel.id === channelId ? updated : channel))
  demoConfig = { ...demoConfig, channel_overrides: demoChannels, updated_at: iso() }
  return updated
}

export async function demoToggleChatbotChannel(channelId: string, isActive: boolean): Promise<ChatbotChannel> {
  return demoUpdateChatbotChannel(channelId, { is_active: isActive })
}

export async function demoListKnowledgeSources(): Promise<ChatbotKnowledgeSourcesResponse> {
  await delay()
  return { data: [...demoKnowledgeSources], count: demoKnowledgeSources.length }
}

export async function demoCreateKnowledgeSource(input: ChatbotKnowledgeSourceInput): Promise<ChatbotKnowledgeSource> {
  await delay()
  const row: ChatbotKnowledgeSource = {
    id: nextId("demo-source"),
    workspace_id: DEMO_WORKSPACE_ID,
    source_type: input.source_type,
    title: input.title,
    source_uri: input.source_uri,
    status: "ready",
    index_version: 4,
    chunk_count: input.source_type === "website" ? 12 : 3,
    error_message: null,
    progress: 100,
    created_at: iso(),
    updated_at: iso(),
    indexed_at: iso(),
  }
  demoKnowledgeSources = [row, ...demoKnowledgeSources]
  return row
}

export async function demoUploadKnowledgeDocument(file: File): Promise<ChatbotKnowledgeSource> {
  return demoCreateKnowledgeSource({ source_type: "document", title: file.name })
}

export async function demoDeleteKnowledgeSource(sourceId: string): Promise<void> {
  await delay()
  demoKnowledgeSources = demoKnowledgeSources.filter((source) => source.id !== sourceId)
}

export async function demoReindexKnowledgeSource(sourceId: string): Promise<ChatbotReindexResponse> {
  await delay()
  demoKnowledgeSources = demoKnowledgeSources.map((source) =>
    source.id === sourceId
      ? { ...source, status: "ready", progress: 100, indexed_at: iso(), updated_at: iso() }
      : source,
  )
  return { job_id: nextId("demo-reindex"), queued: 1, workspace_id: DEMO_WORKSPACE_ID, status: "queued" }
}

export async function demoReindexAllKnowledgeSources(): Promise<ChatbotReindexResponse> {
  await delay()
  demoKnowledgeSources = demoKnowledgeSources.map((source) => ({
    ...source,
    status: "ready",
    progress: 100,
    indexed_at: iso(),
    updated_at: iso(),
  }))
  return {
    job_id: nextId("demo-reindex"),
    queued: demoKnowledgeSources.length,
    workspace_id: DEMO_WORKSPACE_ID,
    status: "queued",
  }
}

export async function demoTestChatbotQuestion(question: string): Promise<ChatbotTestBotResponse> {
  await delay()
  const source = demoKnowledgeSources.find((item) => item.status === "ready") || demoKnowledgeSources[0]
  return {
    answer: `Based on the demo knowledge base, ${question.toLowerCase().includes("pricing")
      ? "pricing depends on usage, connected channels, and lead volume. The bot would escalate detailed quotes to a teammate."
      : "the assistant can answer grounded setup, channel, and lead-capture questions, then escalate when confidence is low."
    }`,
    ai_disclosure: demoConfig.ai_disclosure,
    no_kb: false,
    sources: [
      {
        source_id: source.id,
        source_title: source.title,
        chunk_id: "demo-chunk-1",
        excerpt: "Demo source excerpt used to ground the generated answer.",
        score: 0.84,
      },
    ],
  }
}

export async function demoGetChatbotAnalytics(_range: ChatbotAnalyticsRange = {}): Promise<ChatbotAnalytics> {
  await delay()
  const today = new Date()
  const day = (offset: number) => {
    const value = new Date(today)
    value.setDate(today.getDate() + offset)
    return value.toISOString().slice(0, 10)
  }
  return {
    workspace_id: DEMO_WORKSPACE_ID,
    date_from: day(-6),
    date_to: day(0),
    updated_at: iso(-5),
    totals: {
      conversations: 240,
      containment_rate: 87,
      leads_captured: 31,
      escalations: 18,
      bot_messages: 198,
      opt_outs: 5,
    },
    conversion_funnel: {
      conversations: 240,
      leads_captured: 31,
      prospecting_researched: 18,
      added_to_campaign: 14,
      sequence_enrolled: 11,
      voice_followups: 6,
    },
    timeseries: [
      { date: day(-6), conversations: 21, bot_messages: 18, leads_captured: 3, escalations: 2, opt_outs: 0 },
      { date: day(-5), conversations: 34, bot_messages: 29, leads_captured: 4, escalations: 3, opt_outs: 1 },
      { date: day(-4), conversations: 28, bot_messages: 24, leads_captured: 2, escalations: 1, opt_outs: 0 },
      { date: day(-3), conversations: 41, bot_messages: 35, leads_captured: 6, escalations: 4, opt_outs: 1 },
      { date: day(-2), conversations: 35, bot_messages: 31, leads_captured: 5, escalations: 2, opt_outs: 1 },
      { date: day(-1), conversations: 39, bot_messages: 33, leads_captured: 7, escalations: 3, opt_outs: 1 },
      { date: day(0), conversations: 42, bot_messages: 28, leads_captured: 4, escalations: 3, opt_outs: 1 },
    ],
    channel_breakdown: [
      { channel_type: "whatsapp_business", conversations: 146, bot_resolved: 112, escalated: 9, lead_captured: 22, opted_out: 3 },
      { channel_type: "facebook_messenger", conversations: 92, bot_resolved: 77, escalated: 7, lead_captured: 8, opted_out: 2 },
      { channel_type: "telegram", conversations: 23, bot_resolved: 20, escalated: 2, lead_captured: 1, opted_out: 0 },
    ],
  }
}

export async function demoListChatbotThreads(filters: ChatbotThreadFilters = {}): Promise<ChatbotThreadsResponse> {
  await delay()
  const data = demoThreads
    .filter((thread) => !filters.channel_type || filters.channel_type === "all" || thread.channel_type === filters.channel_type)
    .filter((thread) => !filters.status || filters.status === "all" || thread.status === filters.status)
    .map(summarize)
  return { data, count: data.length, next_cursor: null }
}

export async function demoGetChatbotThread(threadId: string): Promise<ChatbotThreadDetail> {
  await delay()
  const thread = demoThreads.find((item) => item.id === threadId)
  if (!thread) throw new Error("Demo thread not found")
  return { ...thread, messages: [...thread.messages] }
}

export async function demoReplyToChatbotThread(threadId: string, text: string) {
  await delay()
  const thread = demoThreads.find((item) => item.id === threadId)
  if (!thread) throw new Error("Demo thread not found")
  const reply = message(nextId("demo-message"), "outbound", "agent", text, 0)
  thread.messages = [...thread.messages, reply]
  thread.status = "agent_active"
  thread.preview = text
  thread.last_message_at = reply.created_at
  return { thread: { ...thread, messages: [...thread.messages] } }
}

export async function demoResolveChatbotThread(threadId: string) {
  await delay()
  const thread = demoThreads.find((item) => item.id === threadId)
  if (!thread) throw new Error("Demo thread not found")
  thread.status = "resolved"
  thread.outcome = thread.outcome || "agent_resolved"
  return { thread: { ...thread, messages: [...thread.messages] } }
}

export async function demoReopenChatbotThread(threadId: string) {
  await delay()
  const thread = demoThreads.find((item) => item.id === threadId)
  if (!thread) throw new Error("Demo thread not found")
  thread.status = "agent_active"
  return { thread: { ...thread, messages: [...thread.messages] } }
}

export async function demoExportChatbotThreads(format: ChatbotExportFormat, filters: ChatbotThreadFilters = {}) {
  const rows = (await demoListChatbotThreads(filters)).data
  const fullRows = rows.flatMap((summary) => {
    const thread = demoThreads.find((item) => item.id === summary.id)
    return (thread?.messages || []).map((item) => ({
      conversation_id: summary.id,
      channel: summary.channel_type,
      visitor_id: summary.visitor_id,
      sender_role: item.sender,
      message_text: item.content || "",
      sent_at: item.created_at,
      bot_confidence: item.bot_confidence ?? "",
    }))
  })
  const content = format === "json"
    ? JSON.stringify(fullRows, null, 2)
    : [
        "conversation_id,channel,visitor_id,sender_role,message_text,sent_at,bot_confidence",
        ...fullRows.map((row) =>
          [
            row.conversation_id,
            row.channel,
            row.visitor_id,
            row.sender_role,
            `"${row.message_text.replace(/"/g, '""')}"`,
            row.sent_at,
            row.bot_confidence,
          ].join(","),
        ),
      ].join("\n")
  return {
    blob: new Blob([content], { type: format === "json" ? "application/json" : "text/csv" }),
    filename: `chatbot-demo-conversations.${format}`,
  }
}

export async function demoStreamChatbotInboxEvents(options: {
  signal: AbortSignal
  onInbox: () => void
  onOpen: () => void
}) {
  options.onOpen()
  const timer = window.setInterval(options.onInbox, 45_000)
  await new Promise<void>((resolve) => {
    options.signal.addEventListener(
      "abort",
      () => {
        window.clearInterval(timer)
        resolve()
      },
      { once: true },
    )
  })
}

export async function demoGetChatbotConfig(): Promise<ChatbotConfig> {
  await delay()
  return { ...demoConfig, channel_overrides: [...demoChannels] }
}

export async function demoUpdateChatbotConfig(input: ChatbotConfigUpdate): Promise<ChatbotConfig> {
  await delay()
  demoConfig = {
    ...demoConfig,
    ...input,
    business_hours: input.business_hours ?? demoConfig.business_hours,
    lead_capture: input.lead_capture ?? demoConfig.lead_capture,
    updated_at: iso(),
  }
  return demoGetChatbotConfig()
}

export async function demoListChatbotOptOuts(): Promise<ChatbotOptOutsResponse> {
  await delay()
  return { data: [...demoOptOuts], count: demoOptOuts.length }
}

export async function demoRemoveChatbotOptOut(optOutId: string) {
  await delay()
  demoOptOuts = demoOptOuts.filter((item) => item.id !== optOutId)
  return { id: optOutId, removed: true }
}

export async function demoListChatbotDeadLetters(): Promise<ChatbotDeadLettersResponse> {
  await delay()
  return { data: [...demoDeadLetters], count: demoDeadLetters.length }
}

export async function demoRetryChatbotDeadLetter(deadLetterId: string) {
  await delay()
  demoDeadLetters = demoDeadLetters.filter((item) => item.id !== deadLetterId)
  return { id: deadLetterId, requeued: true, inbound_queue_key: `chatbot:inbound:${DEMO_WORKSPACE_ID}` }
}
