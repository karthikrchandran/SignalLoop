import { useEffect, useMemo, useState } from "react"
import { Save } from "lucide-react"

import { Button } from "@/components/ui/button"
import { Checkbox } from "@/components/ui/checkbox"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetFooter,
  SheetHeader,
  SheetTitle,
} from "@/components/ui/sheet"
import {
  type ChatbotChannel,
  type ChatbotChannelInput,
  type ChatbotChannelType,
  createChatbotChannel,
  updateChatbotChannel,
} from "@/features/chatbot/api"

type ChannelDefinition = {
  type: ChatbotChannelType
  title: string
  keyLabel: string
  secretLabel: string
  providerFieldLabel: string
  providerFieldKey: string
  supportsVerifyToken: boolean
}

type ChannelConnectionSheetProps = {
  open: boolean
  definition: ChannelDefinition | null
  channel?: ChatbotChannel
  onOpenChange: (open: boolean) => void
  onSaved: () => void
}

export function ChannelConnectionSheet({
  open,
  definition,
  channel,
  onOpenChange,
  onSaved,
}: ChannelConnectionSheetProps) {
  const [displayName, setDisplayName] = useState("")
  const [apiKey, setApiKey] = useState("")
  const [apiSecret, setApiSecret] = useState("")
  const [webhookSecret, setWebhookSecret] = useState("")
  const [verifyToken, setVerifyToken] = useState("")
  const [providerField, setProviderField] = useState("")
  const [isActive, setIsActive] = useState(false)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (!definition || !open) return
    setDisplayName(channel?.display_name ?? definition.title)
    setApiKey("")
    setApiSecret("")
    setWebhookSecret("")
    setVerifyToken(String(channel?.config_json.verify_token ?? ""))
    setProviderField(String(channel?.config_json[definition.providerFieldKey] ?? ""))
    setIsActive(channel?.is_active ?? false)
    setError(null)
  }, [channel, definition, open])

  const canSave = useMemo(() => {
    if (!definition) return false
    if (!displayName.trim()) return false
    if (!channel && !apiKey.trim()) return false
    return true
  }, [apiKey, channel, definition, displayName])

  const save = async () => {
    if (!definition || !canSave) return
    setSaving(true)
    setError(null)
    try {
      const config_json = {
        [definition.providerFieldKey]: providerField.trim(),
        verify_token: verifyToken.trim(),
      }
      if (channel) {
        const body: Partial<ChatbotChannelInput> = {
          display_name: displayName.trim(),
          config_json,
          is_active: isActive,
        }
        if (apiKey.trim()) {
          body.credentials = {
            api_key: apiKey.trim(),
            api_secret: apiSecret.trim() || null,
            webhook_secret: webhookSecret.trim() || null,
          }
        }
        await updateChatbotChannel(channel.id, body)
      } else {
        await createChatbotChannel({
          channel_type: definition.type,
          display_name: displayName.trim(),
          credentials: {
            api_key: apiKey.trim(),
            api_secret: apiSecret.trim() || null,
            webhook_secret: webhookSecret.trim() || apiSecret.trim() || null,
          },
          config_json,
          is_active: isActive,
        })
      }
      onSaved()
      onOpenChange(false)
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : "Failed to save channel")
    } finally {
      setSaving(false)
    }
  }

  return (
    <Sheet open={open} onOpenChange={onOpenChange}>
      <SheetContent className="w-full overflow-y-auto sm:max-w-lg">
        <SheetHeader>
          <SheetTitle>{definition ? `${definition.title} connection` : "Channel connection"}</SheetTitle>
          <SheetDescription>Credentials are encrypted before storage.</SheetDescription>
        </SheetHeader>

        {definition ? (
          <div className="grid gap-5 px-4">
            <div className="grid gap-2">
              <Label htmlFor="channel-display-name">Display name</Label>
              <Input id="channel-display-name" value={displayName} onChange={(event) => setDisplayName(event.target.value)} />
            </div>
            <div className="grid gap-2">
              <Label htmlFor="channel-provider-field">{definition.providerFieldLabel}</Label>
              <Input
                id="channel-provider-field"
                value={providerField}
                onChange={(event) => setProviderField(event.target.value)}
              />
            </div>
            <div className="grid gap-2">
              <Label htmlFor="channel-api-key">{definition.keyLabel}</Label>
              <Input
                id="channel-api-key"
                value={apiKey}
                onChange={(event) => setApiKey(event.target.value)}
                type="password"
                placeholder={channel ? "Leave blank to keep current credential" : ""}
              />
            </div>
            <div className="grid gap-2">
              <Label htmlFor="channel-api-secret">{definition.secretLabel}</Label>
              <Input
                id="channel-api-secret"
                value={apiSecret}
                onChange={(event) => setApiSecret(event.target.value)}
                type="password"
              />
            </div>
            <div className="grid gap-2">
              <Label htmlFor="channel-webhook-secret">Webhook secret</Label>
              <Input
                id="channel-webhook-secret"
                value={webhookSecret}
                onChange={(event) => setWebhookSecret(event.target.value)}
                type="password"
              />
            </div>
            {definition.supportsVerifyToken ? (
              <div className="grid gap-2">
                <Label htmlFor="channel-verify-token">Verify token</Label>
                <Input
                  id="channel-verify-token"
                  value={verifyToken}
                  onChange={(event) => setVerifyToken(event.target.value)}
                  type="password"
                />
              </div>
            ) : null}
            <label className="flex items-center gap-3 text-sm">
              <Checkbox checked={isActive} onCheckedChange={(checked) => setIsActive(checked === true)} />
              Active
            </label>
            {error ? <div className="rounded-lg border border-destructive/40 bg-destructive/10 p-3 text-sm text-destructive">{error}</div> : null}
          </div>
        ) : null}

        <SheetFooter>
          <Button onClick={save} disabled={!canSave || saving} className="gap-2">
            <Save className="size-4" />
            {saving ? "Saving" : "Save & Verify"}
          </Button>
        </SheetFooter>
      </SheetContent>
    </Sheet>
  )
}
