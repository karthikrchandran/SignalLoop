import { expect, test } from "@playwright/test"

test.use({ storageState: { cookies: [], origins: [] } })

test("offers an OIDC sign-in entry point with the current return path", async ({
  page,
}) => {
  await page.goto("/login?returnTo=%2Frevenue-os")

  const oidcButton = page.getByRole("link", {
    name: "Continue with your work account",
  })
  await expect(oidcButton).toBeVisible()
  await expect(oidcButton).toHaveAttribute(
    "href",
    /\/api\/v1\/auth\/oidc\/start\?return_to=%2Frevenue-os/,
  )
})

test("uses organization sign-in as the only entry in OIDC mode", async ({
  page,
}) => {
  test.skip(
    process.env.VITE_AUTH_MODE !== "oidc",
    "This assertion runs against the OIDC-mode frontend build.",
  )
  await page.route("**/api/v1/public/entry", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        display_name: "ARA Global Revenue Workspace",
        headline: "Turn every customer commitment into coordinated action.",
        products: ["CommitArc", "RevenueOS", "SignalLoop"],
      }),
    })
  })
  await page.goto("/login")

  await expect(
    page.getByRole("heading", { name: "ARA Global Revenue Workspace" }),
  ).toBeVisible()
  await expect(
    page.getByRole("link", { name: "Continue with your work account" }),
  ).toBeVisible()
  await expect(page.getByTestId("email-input")).toHaveCount(0)
  await expect(page.getByTestId("password-input")).toHaveCount(0)
  await expect(page.getByRole("link", { name: "Sign up" })).toHaveCount(0)
})
