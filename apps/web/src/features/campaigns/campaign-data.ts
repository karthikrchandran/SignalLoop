import { useCallback, useEffect, useMemo, useRef, useState } from "react"

import { signalloopRequest } from "@/lib/signalloop-api"

export type CampaignLifecycleStatus = "draft" | "active" | "paused"

export type CampaignRecord = {
  id: string
  name: string
  status: string
  workspace_id?: string
  created_at?: string
}

export type CampaignListResponse = {
  data: CampaignRecord[]
  count: number
}

export const campaignLifecycleOrder: CampaignLifecycleStatus[] = [
  "draft",
  "active",
  "paused",
]

const campaignLifecycleMeta: Record<
  CampaignLifecycleStatus,
  {
    label: string
    title: string
    description: string
    tone: "info" | "ready" | "warning"
    nextStep: string
    route: string
  }
> = {
  draft: {
    label: "Draft",
    title: "Draft campaigns",
    description: "Campaigns still being assembled before launch.",
    tone: "info",
    nextStep: "Finish audience and launch setup",
    route: "/campaigns/draft",
  },
  active: {
    label: "Running",
    title: "Running campaigns",
    description: "Campaigns currently in market and worth checking first.",
    tone: "ready",
    nextStep: "Review progress and pause if needed",
    route: "/campaigns/running",
  },
  paused: {
    label: "Paused",
    title: "Paused campaigns",
    description: "Campaigns held back until the team is ready to resume.",
    tone: "warning",
    nextStep: "Resume, revise, or leave paused",
    route: "/campaigns/paused",
  },
}

export function normalizeCampaignStatus(status: string): CampaignLifecycleStatus | null {
  if (status === "draft" || status === "active" || status === "paused") {
    return status
  }
  return null
}

export function getCampaignLifecycleMeta(status: CampaignLifecycleStatus) {
  return campaignLifecycleMeta[status]
}

export function getCampaignLifecycleTitle(status: CampaignLifecycleStatus) {
  return campaignLifecycleMeta[status].title
}

export function getCampaignLifecycleDescription(status: CampaignLifecycleStatus) {
  return campaignLifecycleMeta[status].description
}

export function getCampaignLifecycleNextStep(status: CampaignLifecycleStatus) {
  return campaignLifecycleMeta[status].nextStep
}

export function getCampaignLifecycleRoute(status: CampaignLifecycleStatus) {
  return campaignLifecycleMeta[status].route
}

export function getCampaignLifecycleLabel(status: CampaignLifecycleStatus) {
  return campaignLifecycleMeta[status].label
}

export function getCampaignLifecycleTone(status: CampaignLifecycleStatus) {
  return campaignLifecycleMeta[status].tone
}

export function formatCampaignDate(value?: string) {
  if (!value) {
    return "-"
  }

  const parsed = new Date(value)
  if (Number.isNaN(parsed.getTime())) {
    return "-"
  }

  return new Intl.DateTimeFormat("en-US", {
    month: "short",
    day: "numeric",
    hour: "numeric",
    minute: "2-digit",
  }).format(parsed)
}

export function useCampaignsWorkspace() {
  const [campaigns, setCampaigns] = useState<CampaignRecord[]>([])
  const [count, setCount] = useState(0)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState("")
  const requestId = useRef(0)

  const loadCampaigns = useCallback(async () => {
    const currentRequestId = requestId.current + 1
    requestId.current = currentRequestId
    setLoading(true)
    setError("")

    try {
      const response = await signalloopRequest<CampaignListResponse>("/api/v1/campaigns/")
      if (requestId.current !== currentRequestId) {
        return
      }

      setCampaigns(response.data)
      setCount(response.count)
    } catch (requestError) {
      if (requestId.current !== currentRequestId) {
        return
      }

      setError(
        requestError instanceof Error
          ? requestError.message
          : "Could not load campaigns",
      )
    } finally {
      if (requestId.current === currentRequestId) {
        setLoading(false)
      }
    }
  }, [])

  useEffect(() => {
    void loadCampaigns()
  }, [loadCampaigns])

  const refresh = useCallback(() => {
    void loadCampaigns()
  }, [loadCampaigns])

  const counts = useMemo(() => {
    const next = {
      draft: 0,
      active: 0,
      paused: 0,
    }

    for (const campaign of campaigns) {
      const lifecycleStatus = normalizeCampaignStatus(campaign.status)
      if (lifecycleStatus) {
        next[lifecycleStatus] += 1
      }
    }

    return next
  }, [campaigns])

  return {
    campaigns,
    count,
    loading,
    error,
    refresh,
    setError,
    counts,
  }
}
