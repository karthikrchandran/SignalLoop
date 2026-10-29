const { chromium } = require("@playwright/test")
const assert = require("node:assert/strict")

async function main() {
  const api = "http://127.0.0.1:18017"
  const origin = "http://127.0.0.1:14177"
  const browser = await chromium.launch({ headless: true })
  try {
    const context = await browser.newContext()
    const page = await context.newPage()
    const errors = []
    const failedApi = []
    page.on("pageerror", (error) => errors.push(error.message))
    await page.goto(`${origin}/login`)
    await page.getByRole("heading", { name: "Sign in to SignalLoop" }).waitFor()
    assert.equal(await page.getByTestId("password-input").count(), 0)
    const passwordLogin = await context.request.post(`${api}/api/v1/login/access-token`, {
      form: { username: "gate-admin@example.com", password: "not-an-authentication-path" },
    })
    assert.equal(passwordLogin.status(), 404)
    const denied = await context.request.get(`${api}/api/v1/users/me`)
    assert.equal(denied.status(), 401)
    await context.addCookies([
      { name: "access_token", value: process.env.GATE_SESSION, url: api, httpOnly: true, sameSite: "Lax" },
      { name: "signalloop_authenticated", value: "1", url: origin, sameSite: "Lax" },
    ])
    page.on("response", (response) => {
      if (response.url().startsWith(`${api}/api/`) && response.status() >= 500) {
        failedApi.push(`${response.status()} ${new URL(response.url()).pathname}`)
      }
    })
    for (const path of ["/users/me", "/campaigns", "/contacts"]) {
      const response = await context.request.get(`${api}/api/v1${path}`, {
        headers: { "X-Workspace-Id": "default" },
      })
      assert.equal(response.status(), 200, path)
    }
    for (const path of ["/dashboard", "/contacts", "/campaigns", "/prospecting"]) {
      await page.goto(`${origin}${path}`)
      await page.waitForLoadState("networkidle")
      assert(!page.url().includes("/login"), path)
      assert((await page.locator("main").first().innerText()).trim().length > 20, path)
    }
    const secondContact = page.getByRole("button", { name: /Gate Two/ })
    await secondContact.focus()
    await page.keyboard.press("Enter")
    assert.equal(await secondContact.getAttribute("aria-pressed"), "true")
    await page.getByRole("checkbox", { name: /^Select Gate One/ }).check()
    assert.equal(await secondContact.getAttribute("aria-pressed"), "true")
    const firstContact = page.getByRole("button", { name: /Gate One/ })
    await firstContact.focus()
    await page.keyboard.press("Space")
    assert.equal(await firstContact.getAttribute("aria-pressed"), "true")
    let searches = 0
    page.on("request", (request) => {
      if (request.url().endsWith("/lead-discovery/search")) searches++
    })
    await page.goto(`${origin}/lead-discovery`)
    await page.getByText(/^Apex Nexus/).first().waitFor()
    assert.equal(searches, 1, "initial discovery search must run once")
    await page.locator('input[value="Technology & SaaS"]').fill("Healthcare")
    await page.waitForLoadState("networkidle")
    assert.equal(searches, 1, "editing filters must not trigger a discovery search")
    const searchButton = page.getByRole("button", { name: "Discover High-Fit Leads", exact: true })
    await searchButton.click()
    await page.waitForLoadState("networkidle")
    assert.equal(searches, 2, "explicit discovery search must run once")
    assert.deepEqual(errors, [], "production bundle must have no runtime exceptions")
    assert.deepEqual(failedApi, [], "production routes must have no API server errors")
    await page.screenshot({ path: ".local-services/production-smoke.png", fullPage: true })
    const logout = await context.request.post(`${api}/api/v1/auth/oidc/logout`)
    assert.equal(logout.status(), 204)
    await context.addCookies([
      { name: "access_token", value: process.env.GATE_SESSION, url: api, httpOnly: true, sameSite: "Lax" },
    ])
    const revoked = await context.request.get(`${api}/api/v1/users/me`)
    assert.equal(revoked.status(), 403, "replaying a revoked session must be denied")
    console.log("PASS: production OIDC UI; password login 404; anonymous 401; session API 3/3; browser routes 5/5; prospecting Enter/Space and independent checkbox; discovery request counts; logout/revocation; zero browser exceptions/API 5xx")
    await context.close()
  } finally {
    await browser.close()
  }
}

main().catch((error) => {
  console.error(error.message)
  process.exitCode = 1
})
