const SERVER_SESSION_HINT = "signalloop_authenticated"

export const isOidcMode = () => import.meta.env.VITE_AUTH_MODE === "oidc"

export const hasServerSessionHint = () => {
  if (typeof document === "undefined") return false

  return document.cookie
    .split(";")
    .some((cookie) => cookie.trim() === `${SERVER_SESSION_HINT}=1`)
}

export const clearClientAuthState = () => {
  localStorage.removeItem("access_token")
  // biome-ignore lint/suspicious/noDocumentCookie: this clears only a non-sensitive UI hint.
  document.cookie = `${SERVER_SESSION_HINT}=; Max-Age=0; Path=/; SameSite=Lax`
}
