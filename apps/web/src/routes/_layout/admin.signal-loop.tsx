import { createFileRoute } from "@tanstack/react-router"

import { TenantAdminWorkspacePage } from "@/features/admin/TenantAdminWorkspacePage"

export const Route = createFileRoute("/_layout/admin/signal-loop")({ component: SignalLoopAdmin })

function SignalLoopAdmin() {
  return (
    <TenantAdminWorkspacePage
      title="SignalLoop administration"
      description="Control tenant-specific engagement operations and provider settings."
      sections={["Engagement overview", "Campaigns and sequences", "Channels and providers", "Consent and suppression", "Templates", "Messaging and voice agents", "SignalLoop Audit"]}
    />
  )
}
