import { mkdir } from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";
import dotenv from "dotenv";
import { chromium } from "playwright";

const __filename = fileURLToPath(import.meta.url);
const repoRoot = path.resolve(path.dirname(__filename), "..", "..");
const outputDir = path.join(repoRoot, "docs", "user-guide", "screenshots");
const baseUrl = process.env.SIGNALLOOP_WEB_URL ?? "http://localhost:5173";

dotenv.config({ path: path.join(repoRoot, ".env") });

const publicScreens = [
  ["01-login.png", "/login"],
  ["02-sign-up.png", "/signup"],
  ["03-password-recovery.png", "/recover-password"],
];

const authenticatedScreens = [
  ["04-home.png", "/home"],
  ["05-dashboard.png", "/dashboard"],
  ["06-campaigns.png", "/campaigns"],
  ["07-campaigns-draft.png", "/campaigns/draft"],
  ["08-campaigns-running.png", "/campaigns/running"],
  ["09-campaigns-paused.png", "/campaigns/paused"],
  ["10-signalloop-ai.png", "/signalloop-ai"],
  ["11-customer-360.png", "/customer-360"],
  ["12-sequences.png", "/sequences"],
  ["13-voice-agents.png", "/voice-agents"],
  ["14-meetings.png", "/scheduling"],
  ["15-contacts.png", "/contacts"],
  ["16-lead-preparation.png", "/prospecting"],
  ["17-analytics.png", "/analytics"],
  ["18-reporting.png", "/reporting"],
  ["19-templates.png", "/templates"],
  ["20-controls.png", "/controls"],
  ["21-settings.png", "/settings"],
  ["22-provider-settings.png", "/settings/providers"],
  ["23-messaging-channels.png", "/chatbot/channels"],
  ["24-messaging-knowledge-base.png", "/chatbot/knowledge-base"],
  ["25-messaging-inbox.png", "/chatbot/inbox"],
  ["26-messaging-analytics.png", "/chatbot/analytics"],
  ["27-messaging-settings.png", "/chatbot/settings"],
  ["28-admin.png", "/admin"],
  ["29-admin-members.png", "/admin/members"],
  ["30-admin-products.png", "/admin/products"],
  ["31-admin-security.png", "/admin/security"],
  ["32-admin-messaging.png", "/admin/messaging"],
  ["33-admin-audit.png", "/admin/audit"],
  ["34-admin-branding.png", "/admin/branding"],
  ["35-admin-dead-letters.png", "/admin/chatbot/dead-letters"],
  ["36-admin-commit-arc.png", "/admin/commit-arc"],
  ["37-admin-revenue-os.png", "/admin/revenue-os"],
  ["38-admin-signalloop.png", "/admin/signal-loop"],
  ["39-platform.png", "/platform"],
  ["40-platform-tenants.png", "/platform/tenants"],
  ["41-platform-identity.png", "/platform/identity"],
  ["42-platform-products.png", "/platform/products"],
  ["43-platform-provider-policies.png", "/platform/provider-policies"],
  ["44-platform-support-access.png", "/platform/support-access"],
  ["45-platform-messaging.png", "/platform/messaging"],
  ["46-platform-audit.png", "/platform/audit"],
  ["47-platform-usage-health.png", "/platform/usage-health"],
  ["48-revenue-os.png", "/revenue-os"],
];

const hideDeveloperTools = async (page) => {
  await page.addStyleTag({
    content: `
      [class*="tsqd"], [class*="tsrd"], [data-testid*="tanstack"],
      button[aria-label*="TanStack"], button[title*="TanStack"] { display: none !important; }
    `,
  });
};

const capture = async (page, [filename, route]) => {
  const requestedUrl = new URL(route, baseUrl).href;
  const response = await page.goto(requestedUrl, { waitUntil: "domcontentloaded" });
  await page.waitForLoadState("networkidle", { timeout: 5000 }).catch(() => {});
  await page.waitForTimeout(400);
  await hideDeveloperTools(page);
  await page.screenshot({ path: path.join(outputDir, filename), animations: "disabled" });
  const status = response?.status() ?? "n/a";
  console.log(`${filename} | ${status} | ${page.url()}`);
};

const email = process.env.FIRST_SUPERUSER;
const password = process.env.FIRST_SUPERUSER_PASSWORD;
if (!email || !password) {
  throw new Error("FIRST_SUPERUSER and FIRST_SUPERUSER_PASSWORD must be set in .env");
}

await mkdir(outputDir, { recursive: true });
const browser = await chromium.launch({ headless: true });
try {
  const publicContext = await browser.newContext({ viewport: { width: 1440, height: 1080 } });
  const publicPage = await publicContext.newPage();
  for (const item of publicScreens) await capture(publicPage, item);
  await publicContext.close();

  const context = await browser.newContext({ viewport: { width: 1440, height: 1080 } });
  const page = await context.newPage();
  await page.goto(new URL("/login", baseUrl).href, { waitUntil: "domcontentloaded" });
  await page.getByTestId("email-input").fill(email);
  await page.getByTestId("password-input").fill(password);
  await page.getByRole("button", { name: "Log In" }).click();
  await page.waitForURL(new URL("/", baseUrl).href, { timeout: 15000 });

  for (const item of authenticatedScreens) await capture(page, item);
  await context.close();
} finally {
  await browser.close();
}

console.log(`Captured ${publicScreens.length + authenticatedScreens.length} current SignalLoop screens.`);
