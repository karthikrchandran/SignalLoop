import { Building2 } from "lucide-react"

import { Button } from "@/components/ui/button"

type OidcLoginButtonProps = {
  returnTo?: string
}

const oidcStartUrl = () =>
  import.meta.env.VITE_OIDC_AUTH_URL ||
  `${import.meta.env.VITE_API_URL || ""}/api/v1/auth/oidc/start`

export function buildOidcLoginUrl(returnTo = window.location.pathname) {
  const url = new URL(oidcStartUrl(), window.location.origin)
  url.searchParams.set("return_to", returnTo)
  return url.toString()
}

export function OidcLoginButton({ returnTo }: OidcLoginButtonProps) {
  return (
    <Button asChild variant="outline" className="w-full">
      <a href={buildOidcLoginUrl(returnTo)}>
        <Building2 aria-hidden="true" />
        Continue with your work account
      </a>
    </Button>
  )
}
