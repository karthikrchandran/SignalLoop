import { useEffect, useState } from "react"

import { Button } from "@/components/ui/button"
import { engagehubRequest } from "@/lib/engagehub-api"

type ApprovalRequest = {
  id: string
  status: string
  requested_action: string
  actor_role: string
}

type ApprovalResponse = {
  data: ApprovalRequest[]
}

type ApprovalInboxProps = {
  disabled?: boolean
  onFeedback: (message: string) => void
}

export function ApprovalInbox({ disabled = false, onFeedback }: ApprovalInboxProps) {
  const [requests, setRequests] = useState<ApprovalRequest[]>([])

  const loadRequests = async () => {
    const response = await engagehubRequest<ApprovalResponse>("/api/v1/approvals/")
    setRequests(response.data)
  }

  useEffect(() => {
    loadRequests().catch(() => {
      onFeedback("Could not load approval inbox")
    })
  }, [onFeedback])

  const decide = async (id: string, action: "approve" | "reject") => {
    await engagehubRequest(`/api/v1/approvals/${id}/${action}`, {
      method: "POST",
      idempotent: true,
      body: { notes: `${action}d from Governance inbox` },
    })
    onFeedback(`Request ${action}d.`)
    await loadRequests()
  }

  return (
    <div className="space-y-2">
      {requests.length === 0 && <p className="text-sm text-muted-foreground">No pending approvals.</p>}
      {requests.map((request) => (
        <div key={request.id} className="rounded border p-2 text-sm">
          <p className="font-medium">{request.requested_action}</p>
          <p className="text-muted-foreground">Role: {request.actor_role} | Status: {request.status}</p>
          {request.status === "pending" && (
            <div className="mt-2 flex gap-2">
              <Button size="sm" disabled={disabled} onClick={() => decide(request.id, "approve")}>Approve</Button>
              <Button size="sm" variant="outline" disabled={disabled} onClick={() => decide(request.id, "reject")}>Reject</Button>
            </div>
          )}
        </div>
      ))}
    </div>
  )
}
