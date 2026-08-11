import { createFileRoute } from "@tanstack/react-router"

import { TenantAdminWorkspacePage } from "@/features/admin/TenantAdminWorkspacePage"

export const Route = createFileRoute("/_layout/platform/provider-policies")({ component: ProviderPolicies })

function ProviderPolicies() {
  return (
    <TenantAdminWorkspacePage
      title="Provider policies"
      description="Define provider use, credential, and fallback policy across the suite."
      sections={["Provider catalog", "Credential requirements", "Fallback policy", "Provider audit"]}
    />
  )
}
