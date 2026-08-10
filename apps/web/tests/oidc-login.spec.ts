import { expect, test } from "@playwright/test"

test.use({ storageState: { cookies: [], origins: [] } })

test("offers an OIDC sign-in entry point with the current return path", async ({
  page,
}) => {
  await page.goto("/login?returnTo=%2Frevenue-os")

  const oidcButton = page.getByRole("link", {
    name: "Continue with organization sign-in",
  })
  await expect(oidcButton).toBeVisible()
  await expect(oidcButton).toHaveAttribute(
    "href",
    /\/api\/v1\/auth\/oidc\/start\?return_to=%2Frevenue-os/,
  )
})
