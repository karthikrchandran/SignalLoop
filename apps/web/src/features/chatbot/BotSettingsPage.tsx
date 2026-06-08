import { Bot, Save, Undo2 } from "lucide-react"
import { toast } from "sonner"

import { Button } from "@/components/ui/button"
import { Checkbox } from "@/components/ui/checkbox"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Separator } from "@/components/ui/separator"
import { Skeleton } from "@/components/ui/skeleton"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { Textarea } from "@/components/ui/textarea"
import { OptOutsTab } from "@/features/chatbot/OptOutsTab"
import { useBotConfig } from "@/features/chatbot/hooks/useBotConfig"

function keywordString(values: string[]) {
  return values.join(", ")
}

function parseKeywords(value: string) {
  return value.split(",").map((item) => item.trim()).filter(Boolean)
}

export default function BotSettingsPage() {
  const settings = useBotConfig()
  const draft = settings.draft

  const errors = {
    ai_disclosure: draft && draft.ai_disclosure.trim().length < 10 ? "Disclosure must be at least 10 characters." : "",
    privacy_policy_url:
      draft?.lead_capture.privacy_policy_url && !/^https?:\/\/.+/i.test(draft.lead_capture.privacy_policy_url)
        ? "Use a valid http or https URL."
        : "",
    retention_days: draft && draft.retention_days < 30 ? "Retention must be at least 30 days." : "",
    token_cap_per_session: draft && draft.token_cap_per_session < 1 ? "Token cap must be positive." : "",
  }
  const hasErrors = Object.values(errors).some(Boolean)

  const save = async () => {
    if (hasErrors) return
    await settings.save()
    toast.success("Bot settings saved")
  }

  const update = (patch: Partial<typeof draft>) => {
    settings.setDraft((current) => (current ? { ...current, ...patch } : current))
  }

  if (settings.loading || !draft) {
    return (
      <div className="space-y-4">
        <Skeleton className="h-12 w-72" />
        <Skeleton className="h-96 w-full" />
      </div>
    )
  }

  return (
    <div className="relative flex flex-col gap-6 pb-20">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <p className="text-sm font-medium text-muted-foreground">Messaging Hub</p>
          <h1 className="flex items-center gap-2 text-2xl font-bold tracking-tight">
            <Bot className="size-6 text-muted-foreground" />
            Bot Settings
          </h1>
        </div>
        <Button onClick={save} disabled={!settings.dirty || hasErrors || settings.saving} className="gap-2">
          <Save className="size-4" />
          Save Changes
        </Button>
      </div>

      {settings.error ? (
        <div className="rounded-lg border border-destructive/40 bg-destructive/10 p-3 text-sm text-destructive">
          {settings.error}
        </div>
      ) : null}

      <Tabs defaultValue="settings" className="gap-4">
        <TabsList>
          <TabsTrigger value="settings">Settings</TabsTrigger>
          <TabsTrigger value="opt-outs">Opt-outs</TabsTrigger>
        </TabsList>

        <TabsContent value="settings" className="space-y-6">
          <section className="space-y-4">
            <div>
              <h2 className="text-base font-semibold">AI & Disclosure</h2>
              <p className="text-sm text-muted-foreground">Workspace-level assistant identity and central cost guardrails.</p>
            </div>
            <div className="grid gap-4 md:grid-cols-2">
              <div className="space-y-2">
                <Label htmlFor="bot-name">Bot name</Label>
                <Input id="bot-name" value={draft.bot_name} onChange={(event) => update({ bot_name: event.target.value })} />
              </div>
              <div className="space-y-2">
                <Label htmlFor="token-cap">Token cap per session</Label>
                <Input
                  id="token-cap"
                  type="number"
                  value={draft.token_cap_per_session}
                  onChange={(event) => update({ token_cap_per_session: Number(event.target.value) })}
                />
                {errors.token_cap_per_session ? <p className="text-xs text-destructive">{errors.token_cap_per_session}</p> : null}
              </div>
            </div>
            <div className="space-y-2">
              <Label htmlFor="ai-disclosure">AI disclosure text</Label>
              <Input id="ai-disclosure" value={draft.ai_disclosure} onChange={(event) => update({ ai_disclosure: event.target.value })} />
              {errors.ai_disclosure ? <p className="text-xs text-destructive">{errors.ai_disclosure}</p> : null}
            </div>
            <div className="space-y-2">
              <Label htmlFor="persona">Persona</Label>
              <Textarea id="persona" value={draft.persona || ""} onChange={(event) => update({ persona: event.target.value })} />
            </div>
          </section>

          <Separator />

          <section className="space-y-4">
            <div>
              <h2 className="text-base font-semibold">Lead Capture</h2>
              <p className="text-sm text-muted-foreground">Consent-first capture and intent detection.</p>
            </div>
            <div className="flex items-center gap-2">
              <Checkbox
                checked={draft.lead_capture.enabled}
                onCheckedChange={(checked) => update({ lead_capture: { ...draft.lead_capture, enabled: checked === true } })}
              />
              <Label>Enable lead capture</Label>
            </div>
            <div className="grid gap-4 md:grid-cols-2">
              <div className="space-y-2">
                <Label htmlFor="min-turns">Minimum turns</Label>
                <Input
                  id="min-turns"
                  type="number"
                  value={draft.lead_capture.min_turns}
                  onChange={(event) => update({ lead_capture: { ...draft.lead_capture, min_turns: Number(event.target.value) } })}
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="keywords">Intent keywords</Label>
                <Input
                  id="keywords"
                  value={keywordString(draft.lead_capture.intent_keywords)}
                  onChange={(event) => update({ lead_capture: { ...draft.lead_capture, intent_keywords: parseKeywords(event.target.value) } })}
                />
              </div>
            </div>
            <div className="space-y-2">
              <Label htmlFor="privacy-url">Privacy policy URL</Label>
              <Input
                id="privacy-url"
                value={draft.lead_capture.privacy_policy_url || ""}
                onChange={(event) => update({ lead_capture: { ...draft.lead_capture, privacy_policy_url: event.target.value } })}
              />
              {errors.privacy_policy_url ? <p className="text-xs text-destructive">{errors.privacy_policy_url}</p> : null}
            </div>
          </section>

          <Separator />

          <section className="space-y-4">
            <div>
              <h2 className="text-base font-semibold">Business Hours</h2>
              <p className="text-sm text-muted-foreground">Out-of-hours handoff behavior.</p>
            </div>
            <div className="flex items-center gap-2">
              <Checkbox
                checked={draft.business_hours.enabled}
                onCheckedChange={(checked) => update({ business_hours: { ...draft.business_hours, enabled: checked === true } })}
              />
              <Label>Enable out-of-hours mode</Label>
            </div>
            <div className="grid gap-4 md:grid-cols-3">
              <div className="space-y-2">
                <Label htmlFor="timezone">Timezone</Label>
                <Input
                  id="timezone"
                  value={draft.business_hours.timezone}
                  onChange={(event) => update({ business_hours: { ...draft.business_hours, timezone: event.target.value } })}
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="start">Start</Label>
                <Input
                  id="start"
                  type="time"
                  value={draft.business_hours.start}
                  onChange={(event) => update({ business_hours: { ...draft.business_hours, start: event.target.value } })}
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="end">End</Label>
                <Input
                  id="end"
                  type="time"
                  value={draft.business_hours.end}
                  onChange={(event) => update({ business_hours: { ...draft.business_hours, end: event.target.value } })}
                />
              </div>
            </div>
            <div className="space-y-2">
              <Label htmlFor="out-of-hours">Out-of-hours message</Label>
              <Textarea
                id="out-of-hours"
                value={draft.out_of_hours_message || ""}
                onChange={(event) => update({ out_of_hours_message: event.target.value })}
              />
            </div>
          </section>

          <Separator />

          <section className="space-y-4">
            <div>
              <h2 className="text-base font-semibold">Compliance</h2>
              <p className="text-sm text-muted-foreground">Retention and re-index defaults.</p>
            </div>
            <div className="grid gap-4 md:grid-cols-2">
              <div className="space-y-2">
                <Label htmlFor="retention">Retention days</Label>
                <Input
                  id="retention"
                  type="number"
                  value={draft.retention_days}
                  onChange={(event) => update({ retention_days: Number(event.target.value) })}
                />
                {errors.retention_days ? <p className="text-xs text-destructive">{errors.retention_days}</p> : null}
              </div>
              <div className="space-y-2">
                <Label htmlFor="reindex">Re-index schedule</Label>
                <Input
                  id="reindex"
                  type="time"
                  value={draft.reindex_schedule_time}
                  onChange={(event) => update({ reindex_schedule_time: event.target.value })}
                />
              </div>
            </div>
          </section>
        </TabsContent>

        <TabsContent value="opt-outs">
          <OptOutsTab />
        </TabsContent>
      </Tabs>

      {settings.dirty ? (
        <div className="fixed inset-x-4 bottom-4 z-40 mx-auto flex max-w-5xl items-center justify-between gap-3 rounded-lg border bg-background p-3 shadow-lg">
          <span className="text-sm font-medium">You have unsaved changes.</span>
          <div className="flex gap-2">
            <Button variant="outline" onClick={settings.discard} className="gap-2">
              <Undo2 className="size-4" />
              Discard
            </Button>
            <Button onClick={save} disabled={hasErrors || settings.saving} className="gap-2">
              <Save className="size-4" />
              Save Changes
            </Button>
          </div>
        </div>
      ) : null}
    </div>
  )
}
