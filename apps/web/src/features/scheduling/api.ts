import { signalloopRequest } from "@/lib/signalloop-api"

export type SchedulingRequestStatus =
  | "pending"
  | "link_sent"
  | "booked"
  | "cancelled"

export type SchedulingRequestSource = "voice_call" | "email_reply" | "manual"

export type SchedulingRequest = {
  id: string
  workspace_id: string
  calendly_state: string | null
  contact_id: string
  campaign_id: string
  signal_event_id: string | null
  status: SchedulingRequestStatus
  source: SchedulingRequestSource
  meeting_link: string | null
  calendly_event_id: string | null
  meeting_datetime: string | null
  assigned_to_email: string | null
  notes: string | null
  created_at: string
  updated_at: string
}

export function withCalendlyState(url: string, state: string): string {
  try {
    const parsed = new URL(url)
    parsed.searchParams.set("utm_content", state)
    return parsed.toString()
  } catch {
    return url
  }
}

export type SchedulingRequestsResponse = {
  data: SchedulingRequest[]
  count: number
}

export type SchedulingRequestUpdate = {
  status?: SchedulingRequestStatus
  meeting_link?: string | null
  assigned_to_email?: string | null
  notes?: string | null
}

export async function listSchedulingRequests(params?: {
  status?: SchedulingRequestStatus
  campaign_id?: string
  skip?: number
  limit?: number
}): Promise<SchedulingRequestsResponse> {
  const query = new URLSearchParams()
  if (params?.status) query.set("status", params.status)
  if (params?.campaign_id) query.set("campaign_id", params.campaign_id)
  if (params?.skip != null) query.set("skip", String(params.skip))
  if (params?.limit != null) query.set("limit", String(params.limit))
  const qs = query.toString()
  return signalloopRequest<SchedulingRequestsResponse>(
    `/api/v1/scheduling/requests${qs ? `?${qs}` : ""}`,
  )
}

export async function updateSchedulingRequest(
  id: string,
  data: SchedulingRequestUpdate,
): Promise<SchedulingRequest> {
  return signalloopRequest<SchedulingRequest>(
    `/api/v1/scheduling/requests/${id}`,
    {
      method: "PATCH",
      body: data,
    },
  )
}
