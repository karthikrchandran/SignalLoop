import { useState } from "react"
import { AlertCircle, BellOff, CheckCircle2, PauseCircle, PlayCircle, Send, ShieldCheck } from "lucide-react"

import { Alert } from "@/components/ui/alert"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { engagehubRequest } from "@/lib/engagehub-api"

const TIMEZONES = [
  "UTC",
  "America/New_York",
  "America/Chicago",
  "America/Denver",
  "America/Los_Angeles",
  "America/Phoenix",
  "Europe/London",
  "Europe/Paris",
  "Europe/Berlin",
  "Asia/Kolkata",
  "Asia/Singapore",
  "Asia/Tokyo",
  "Australia/Sydney",
]

export default function GovernanceControlPage() {
  // Sending limits
  const [campaignCap, setCampaignCap] = useState("1000")
  const [systemCap, setSystemCap] = useState("5000")
  const [limitsSaved, setLimitsSaved] = useState(false)

  // Quiet hours
  const [quietStart, setQuietStart] = useState("21:00")
  const [quietEnd, setQuietEnd] = useState("08:00")
  const [quietTimezone, setQuietTimezone] = useState("UTC")
  const [quietSaved, setQuietSaved] = useState(false)

  // Emergency controls
  const [pauseReason, setPauseReason] = useState("")
  const [systemPaused, setSystemPaused] = useState(false)

  const [feedback, setFeedback] = useState("")
  const [busy, setBusy] = useState(false)

  const run = async (action: () => Promise<void>) => {
    setBusy(true)
    setFeedback("")
    try {
      await action()
    } catch (error) {
      setFeedback(error instanceof Error ? error.message : "Something went wrong. Please try again.")
    } finally {
      setBusy(false)
    }
  }

  const saveLimits = () =>
    run(async () => {
      await engagehubRequest("/api/v1/policies/", {
        method: "POST",
        idempotent: true,
        body: {
          scope: "workspace",
          policy_type: "daily_caps",
          payload_json: {
            campaignDailyCap: Number(campaignCap),
            systemDailyCap: Number(systemCap),
          },
        },
      })
      setLimitsSaved(true)
      setTimeout(() => setLimitsSaved(false), 3000)
    })

  const saveQuietHours = () =>
    run(async () => {
      await engagehubRequest("/api/v1/policies/", {
        method: "POST",
        idempotent: true,
        body: {
          scope: "workspace",
          policy_type: "quiet_hours",
          payload_json: { start: quietStart, end: quietEnd, timezone: quietTimezone },
        },
      })
      setQuietSaved(true)
      setTimeout(() => setQuietSaved(false), 3000)
    })

  const pauseAll = () =>
    run(async () => {
      await engagehubRequest("/api/v1/controls/pause", {
        method: "POST",
        idempotent: true,
        body: { paused_reason: pauseReason || "Paused by admin" },
      })
      setSystemPaused(true)
      setFeedback("All outreach has been paused. No emails or calls will go out until you resume.")
    })

  const resumeAll = () =>
    run(async () => {
      await engagehubRequest("/api/v1/controls/resume", {
        method: "POST",
        idempotent: true,
      })
      setSystemPaused(false)
      setFeedback("Outreach has been resumed. Campaigns and sequences will continue normally.")
    })

  return (
    <div className="flex flex-col gap-6">
      <div>
        <h1 className="text-3xl font-semibold tracking-tight">Outreach Controls</h1>
        <p className="max-w-3xl text-sm text-muted-foreground">
          Manage sending limits, quiet hours, and emergency controls for all outreach activities.
        </p>
      </div>

      {/* Daily sending limits */}
      <Card>
        <CardHeader>
          <div className="flex items-center gap-3">
            <div className="flex size-9 shrink-0 items-center justify-center rounded-lg bg-primary/10">
              <Send className="size-5 text-primary" />
            </div>
            <div>
              <CardTitle>Daily sending limits</CardTitle>
              <CardDescription>
                Cap the number of messages sent each day to protect your sender reputation and avoid spam flags.
              </CardDescription>
            </div>
          </div>
        </CardHeader>
        <CardContent className="grid gap-5 md:grid-cols-2">
          <div className="space-y-1">
            <Label htmlFor="campaignCap">Max emails per campaign per day</Label>
            <p className="text-xs text-muted-foreground">Each individual campaign will stop sending after this many emails.</p>
            <Input
              id="campaignCap"
              type="number"
              min={1}
              value={campaignCap}
              onChange={(e) => setCampaignCap(e.target.value)}
            />
          </div>
          <div className="space-y-1">
            <Label htmlFor="systemCap">Max total emails across all campaigns</Label>
            <p className="text-xs text-muted-foreground">A system-wide ceiling — once reached, no more emails go out that day.</p>
            <Input
              id="systemCap"
              type="number"
              min={1}
              value={systemCap}
              onChange={(e) => setSystemCap(e.target.value)}
            />
          </div>
          <div className="md:col-span-2">
            <Button onClick={saveLimits} disabled={busy}>
              {limitsSaved ? (
                <><CheckCircle2 className="mr-2 size-4" /> Saved</>
              ) : (
                "Save limits"
              )}
            </Button>
          </div>
        </CardContent>
      </Card>

      {/* Quiet hours */}
      <Card>
        <CardHeader>
          <div className="flex items-center gap-3">
            <div className="flex size-9 shrink-0 items-center justify-center rounded-lg bg-primary/10">
              <BellOff className="size-5 text-primary" />
            </div>
            <div>
              <CardTitle>Do not disturb hours</CardTitle>
              <CardDescription>
                No emails or calls will go out during this window, even if a campaign is scheduled to run.
              </CardDescription>
            </div>
          </div>
        </CardHeader>
        <CardContent className="grid gap-5 md:grid-cols-3">
          <div className="space-y-1">
            <Label htmlFor="quietStart">Stop sending at</Label>
            <Input id="quietStart" type="time" value={quietStart} onChange={(e) => setQuietStart(e.target.value)} />
          </div>
          <div className="space-y-1">
            <Label htmlFor="quietEnd">Resume sending at</Label>
            <Input id="quietEnd" type="time" value={quietEnd} onChange={(e) => setQuietEnd(e.target.value)} />
          </div>
          <div className="space-y-1">
            <Label htmlFor="quietTz">Timezone</Label>
            <select
              id="quietTz"
              value={quietTimezone}
              onChange={(e) => setQuietTimezone(e.target.value)}
              className="flex h-9 w-full rounded-md border border-input bg-transparent px-3 py-1 text-sm shadow-xs transition-colors focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
            >
              {TIMEZONES.map((tz) => (
                <option key={tz} value={tz}>{tz.replace(/_/g, " ")}</option>
              ))}
            </select>
          </div>
          <div className="md:col-span-3">
            <Button onClick={saveQuietHours} disabled={busy}>
              {quietSaved ? (
                <><CheckCircle2 className="mr-2 size-4" /> Saved</>
              ) : (
                "Save quiet hours"
              )}
            </Button>
          </div>
        </CardContent>
      </Card>

      {/* Emergency controls */}
      <Card className={systemPaused ? "border-destructive/50 bg-destructive/5" : undefined}>
        <CardHeader>
          <div className="flex items-center gap-3">
            <div className={`flex size-9 shrink-0 items-center justify-center rounded-lg ${systemPaused ? "bg-destructive/10" : "bg-primary/10"}`}>
              <ShieldCheck className={`size-5 ${systemPaused ? "text-destructive" : "text-primary"}`} />
            </div>
            <div>
              <CardTitle>Emergency controls</CardTitle>
              <CardDescription>
                Instantly stop or restart all outreach across every campaign and sequence. Use this during compliance holds or unexpected issues.
              </CardDescription>
            </div>
          </div>
        </CardHeader>
        <CardContent className="space-y-4">
          {systemPaused && (
            <div className="flex items-center gap-2 rounded-md border border-destructive/30 bg-destructive/10 px-3 py-2 text-sm font-medium text-destructive">
              <AlertCircle className="size-4 shrink-0" />
              All outreach is currently paused — no emails or calls are being sent.
            </div>
          )}
          <div className="space-y-1">
            <Label htmlFor="pauseReason">Reason for pausing <span className="text-muted-foreground font-normal">(optional)</span></Label>
            <p className="text-xs text-muted-foreground">Logged internally for your records. Not shown to contacts.</p>
            <Input
              id="pauseReason"
              placeholder="e.g. Compliance review, system maintenance…"
              value={pauseReason}
              onChange={(e) => setPauseReason(e.target.value)}
              disabled={systemPaused}
            />
          </div>
          <div className="flex gap-3">
            <Button variant="destructive" onClick={pauseAll} disabled={busy || systemPaused}>
              <PauseCircle className="mr-2 size-4" />
              Pause all outreach
            </Button>
            <Button variant="outline" onClick={resumeAll} disabled={busy || !systemPaused}>
              <PlayCircle className="mr-2 size-4" />
              Resume outreach
            </Button>
          </div>
        </CardContent>
      </Card>

      {feedback && (
        <Alert>
          <p className="text-sm">{feedback}</p>
        </Alert>
      )}
    </div>
  )
}
