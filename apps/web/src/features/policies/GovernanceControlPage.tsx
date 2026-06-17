import { useState } from "react"
import { AlertCircle, PauseCircle, PlayCircle, ShieldCheck } from "lucide-react"

import { Alert } from "@/components/ui/alert"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { signalloopRequest } from "@/lib/signalloop-api"

export default function GovernanceControlPage() {
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

  const pauseAll = () =>
    run(async () => {
      await signalloopRequest("/api/v1/controls/pause", {
        method: "POST",
        idempotent: true,
        body: { paused_reason: pauseReason || "Paused by admin" },
      })
      setSystemPaused(true)
      setFeedback("All outreach has been paused. No emails or calls will go out until you resume.")
    })

  const resumeAll = () =>
    run(async () => {
      await signalloopRequest("/api/v1/controls/resume", {
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
          Pause or resume outbound activity across campaigns and sequences.
        </p>
      </div>

      {/* Emergency controls */}
      <Card className={systemPaused ? "border-destructive/50 bg-destructive/5" : undefined}>
        <CardHeader>
          <div className="flex items-center gap-3">
            <div className={`flex size-9 shrink-0 items-center justify-center rounded-lg ${systemPaused ? "bg-destructive/10" : "bg-primary/10"}`}>
              <ShieldCheck className={`size-5 ${systemPaused ? "text-destructive" : "text-primary"}`} />
            </div>
            <div>
              <CardTitle>Emergency pause</CardTitle>
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

      <Card>
        <CardHeader>
          <CardTitle>Policy settings</CardTitle>
          <CardDescription>
            Daily limits and quiet hours are enforced by backend configuration in this build.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <p className="text-sm text-muted-foreground">
            Editing those policies from the UI requires a supported controls API. This page exposes only the supported pause and resume controls.
          </p>
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
