import { useEffect, useState } from "react"
import { CheckCheck, PauseCircle, PlayCircle } from "lucide-react"

import { Alert } from "@/components/ui/alert"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { ApprovalInbox } from "@/features/policies/components/ApprovalInbox"
import { QuietHoursEditor } from "@/features/policies/components/QuietHoursEditor"
import { engagehubRequest } from "@/lib/engagehub-api"

type Policy = {
  id: string
  scope: string
  policy_type: string
  status: string
  payload_json: Record<string, unknown>
}

type PoliciesResponse = { data: Policy[] }

type PolicyDecision = {
  allowed: boolean
  reason_code: string | null
  semantic_error: string | null
}

export default function GovernanceControlPage() {
  const [policies, setPolicies] = useState<Policy[]>([])
  const [scope, setScope] = useState("workspace")
  const [policyType, setPolicyType] = useState("daily_caps")
  const [payloadJson, setPayloadJson] = useState('{"campaignDailyCap":1000,"systemDailyCap":5000}')
  const [quietHoursStart, setQuietHoursStart] = useState("21:00")
  const [quietHoursEnd, setQuietHoursEnd] = useState("08:00")
  const [quietHoursTimezone, setQuietHoursTimezone] = useState("UTC")
  const [pausedReason, setPausedReason] = useState("Compliance hold")
  const [decision, setDecision] = useState<PolicyDecision | null>(null)
  const [feedback, setFeedback] = useState("")
  const [busy, setBusy] = useState(false)

  const loadPolicies = async () => {
    const response = await engagehubRequest<PoliciesResponse>("/api/v1/policies/")
    setPolicies(response.data)
  }

  useEffect(() => {
    loadPolicies().catch((error) => {
      setFeedback(error instanceof Error ? error.message : "Could not load policies")
    })
  }, [])

  const run = async (action: () => Promise<void>) => {
    setBusy(true)
    setFeedback("")
    try {
      await action()
    } catch (error) {
      setFeedback(error instanceof Error ? error.message : "Unexpected error")
    } finally {
      setBusy(false)
    }
  }

  const createPolicy = async () => {
    await run(async () => {
      const payload =
        policyType === "quiet_hours"
          ? {
              start: quietHoursStart,
              end: quietHoursEnd,
              timezone: quietHoursTimezone,
            }
          : JSON.parse(payloadJson)

      await engagehubRequest("/api/v1/policies/", {
        method: "POST",
        idempotent: true,
        body: {
          scope,
          policy_type: policyType,
          payload_json: payload,
        },
      })
      await loadPolicies()
      setFeedback("Governance policy saved.")
    })
  }

  const evaluateDecision = async () => {
    await run(async () => {
      const response = await engagehubRequest<PolicyDecision>("/api/v1/policies/evaluate", {
        method: "POST",
      })
      setDecision(response)
      setFeedback("Policy decision evaluated.")
    })
  }

  const pauseGlobal = async () => {
    await run(async () => {
      await engagehubRequest("/api/v1/controls/pause", {
        method: "POST",
        idempotent: true,
        body: { paused_reason: pausedReason },
      })
      setFeedback("Global pause applied.")
    })
  }

  const resumeGlobal = async () => {
    await run(async () => {
      await engagehubRequest("/api/v1/controls/resume", {
        method: "POST",
        idempotent: true,
      })
      setFeedback("Global resume applied.")
    })
  }

  return (
    <div className="flex flex-col gap-6">
      <div>
        <h1 className="text-3xl font-semibold tracking-tight">Governance controls</h1>
        <p className="max-w-3xl text-sm text-muted-foreground">
          Configure policy rules, evaluate enforcement outcomes, and apply global pause/resume controls with explicit reason codes.
        </p>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Policy registry</CardTitle>
          <CardDescription>Create and track policy records scoped to workspace or campaign context.</CardDescription>
        </CardHeader>
        <CardContent className="grid gap-3 md:grid-cols-2">
          <div>
            <Label htmlFor="scope">Scope</Label>
            <Input id="scope" value={scope} onChange={(event) => setScope(event.target.value)} />
          </div>
          <div>
            <Label htmlFor="policyType">Policy type</Label>
            <Input id="policyType" value={policyType} onChange={(event) => setPolicyType(event.target.value)} />
          </div>
          <div className="md:col-span-2">
            <Label htmlFor="payloadJson">Policy payload JSON</Label>
            <Input id="payloadJson" value={payloadJson} onChange={(event) => setPayloadJson(event.target.value)} />
          </div>
          {policyType === "quiet_hours" && (
            <div className="md:col-span-2">
              <QuietHoursEditor
                start={quietHoursStart}
                end={quietHoursEnd}
                timezone={quietHoursTimezone}
                disabled={busy}
                onChange={({ start, end, timezone }) => {
                  setQuietHoursStart(start)
                  setQuietHoursEnd(end)
                  setQuietHoursTimezone(timezone)
                }}
              />
            </div>
          )}
          <div className="md:col-span-2 flex gap-2">
            <Button onClick={createPolicy} disabled={busy}>
              <CheckCheck className="mr-2 size-4" /> Save policy
            </Button>
            <Button variant="outline" onClick={evaluateDecision} disabled={busy}>
              Evaluate decision
            </Button>
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Global controls</CardTitle>
        </CardHeader>
        <CardContent className="space-y-3">
          <div>
            <Label htmlFor="pausedReason">Pause reason</Label>
            <Input id="pausedReason" value={pausedReason} onChange={(event) => setPausedReason(event.target.value)} />
          </div>
          <div className="flex gap-2">
            <Button onClick={pauseGlobal} disabled={busy}>
              <PauseCircle className="mr-2 size-4" /> Pause all
            </Button>
            <Button variant="outline" onClick={resumeGlobal} disabled={busy}>
              <PlayCircle className="mr-2 size-4" /> Resume all
            </Button>
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Current policies</CardTitle>
        </CardHeader>
        <CardContent className="space-y-2 text-sm">
          {policies.map((policy) => (
            <div key={policy.id} className="rounded border p-2">
              <p className="font-medium">{policy.policy_type} ({policy.scope})</p>
              <p className="text-muted-foreground">Status: {policy.status}</p>
            </div>
          ))}
          {decision && (
            <div className="rounded border border-primary/40 p-2">
              <p className="font-medium">Evaluation result</p>
              <p>Allowed: {String(decision.allowed)}</p>
              <p>Reason code: {decision.reason_code || "n/a"}</p>
              <p>Semantic error: {decision.semantic_error || "n/a"}</p>
            </div>
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Approval inbox</CardTitle>
          <CardDescription>Approve or reject governed actions that require elevated permissions.</CardDescription>
        </CardHeader>
        <CardContent>
          <ApprovalInbox disabled={busy} onFeedback={setFeedback} />
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
