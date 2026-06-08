import { useEffect, useMemo, useState } from "react"
import { Bot, MessageCircle, Phone, Send, RefreshCw } from "lucide-react"

import { Button } from "@/components/ui/button"
import {
  type ChatbotChannel,
  type ChatbotChannelType,
  listChatbotChannels,
  toggleChatbotChannel,
} from "@/features/chatbot/api"
import { ChannelCard } from "@/features/chatbot/components/ChannelCard"
import { ChannelConnectionSheet } from "@/features/chatbot/components/ChannelConnectionSheet"

const channelDefinitions = [
  {
    type: "facebook_messenger",
    title: "Facebook Messenger",
    description: "Meta Page Messenger",
    icon: MessageCircle,
    keyLabel: "Page access token",
    secretLabel: "App secret",
    providerFieldLabel: "Page ID",
    providerFieldKey: "page_id",
    supportsVerifyToken: true,
    fallbackStatus: "disconnected",
  },
  {
    type: "whatsapp_business",
    title: "WhatsApp Business",
    description: "Meta Cloud API",
    icon: Phone,
    keyLabel: "Access token",
    secretLabel: "App secret",
    providerFieldLabel: "Phone number ID",
    providerFieldKey: "phone_number_id",
    supportsVerifyToken: true,
    fallbackStatus: "disconnected",
  },
  {
    type: "telegram",
    title: "Telegram",
    description: "Telegram Bot API",
    icon: Send,
    keyLabel: "Bot token",
    secretLabel: "Bot API secret token",
    providerFieldLabel: "Bot username",
    providerFieldKey: "bot_username",
    supportsVerifyToken: false,
    fallbackStatus: "pending_approval",
  },
] as const

type ChannelDefinition = (typeof channelDefinitions)[number]

export default function ChannelsPage() {
  const [channels, setChannels] = useState<ChatbotChannel[]>([])
  const [loading, setLoading] = useState(true)
  const [busyChannel, setBusyChannel] = useState<ChatbotChannelType | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [sheetDefinition, setSheetDefinition] = useState<ChannelDefinition | null>(null)

  const channelsByType = useMemo(
    () => new Map(channels.map((channel) => [channel.channel_type, channel])),
    [channels],
  )

  const loadChannels = async () => {
    setLoading(true)
    setError(null)
    try {
      const response = await listChatbotChannels()
      setChannels(response.data)
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : "Failed to load channels")
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    void loadChannels()
  }, [])

  const toggleChannel = async (channel: ChatbotChannel) => {
    setBusyChannel(channel.channel_type)
    setError(null)
    try {
      await toggleChatbotChannel(channel.id, !channel.is_active)
      await loadChannels()
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : "Failed to update channel")
    } finally {
      setBusyChannel(null)
    }
  }

  return (
    <div className="flex flex-col gap-6">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <p className="text-sm font-medium text-muted-foreground">Messaging Hub</p>
          <h1 className="flex items-center gap-2 text-2xl font-bold tracking-tight">
            <Bot className="size-6 text-muted-foreground" />
            Channels
          </h1>
        </div>
        <Button variant="outline" size="sm" onClick={loadChannels} disabled={loading} className="gap-2">
          <RefreshCw className={loading ? "size-4 animate-spin" : "size-4"} />
          Refresh
        </Button>
      </div>

      {error ? <div className="rounded-lg border border-destructive/40 bg-destructive/10 p-3 text-sm text-destructive">{error}</div> : null}

      <div className="grid gap-4 lg:grid-cols-3">
        {channelDefinitions.map((definition) => {
          const channel = channelsByType.get(definition.type)
          return (
            <ChannelCard
              key={definition.type}
              title={definition.title}
              description={definition.description}
              icon={definition.icon}
              channel={channel}
              fallbackStatus={definition.fallbackStatus}
              busy={busyChannel === definition.type}
              onEdit={() => setSheetDefinition(definition)}
              onToggle={() => channel && void toggleChannel(channel)}
            />
          )
        })}
      </div>

      <ChannelConnectionSheet
        open={sheetDefinition !== null}
        definition={sheetDefinition}
        channel={sheetDefinition ? channelsByType.get(sheetDefinition.type) : undefined}
        onOpenChange={(open) => {
          if (!open) setSheetDefinition(null)
        }}
        onSaved={loadChannels}
      />
    </div>
  )
}
