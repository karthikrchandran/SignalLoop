import { writeFile } from "node:fs/promises";
import path from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";
import { chromium } from "playwright";

const outDir = path.dirname(fileURLToPath(import.meta.url));
const htmlName = "signalloop-ecrm-pricing-brief.html";
const pdfName = "signalloop-ecrm-pricing-brief.pdf";

const styles = `
  @page { size: A4; margin: 0; }
  :root {
    --ink: #14213d;
    --muted: #5f6978;
    --line: #d6dee8;
    --violet: #6550e8;
    --teal: #087f83;
    --ice: #e9f7f6;
    --lilac: #efedff;
    --wash: #f5f7fb;
    --gold: #d89a16;
    --rose: #fff5f5;
  }
  * { box-sizing: border-box; }
  html, body { margin: 0; background: #dfe5ec; color: var(--ink); font-family: "Segoe UI", Arial, sans-serif; }
  .page { width: 210mm; height: 297mm; padding: 42px 52px 34px; background: white; position: relative; overflow: hidden; page-break-after: always; }
  .page::before { content: ""; position: absolute; inset: 0 0 auto; height: 18px; background: linear-gradient(90deg, var(--violet), #7469ef 52%, var(--teal)); }
  h1, h2, h3, p { margin: 0; }
  h1 { font-size: 34px; line-height: 1.05; letter-spacing: 0; margin-top: 10px; }
  h2 { font-size: 19px; line-height: 1.15; letter-spacing: 0; }
  h3 { font-size: 13px; line-height: 1.2; letter-spacing: 0; }
  p, li, td { font-size: 10.5px; line-height: 1.35; }
  .muted { color: var(--muted); }
  .eyebrow { color: var(--violet); text-transform: uppercase; font-size: 12px; font-weight: 800; letter-spacing: 1.3px; }
  .lead { margin-top: 8px; max-width: 670px; font-size: 14px; line-height: 1.4; color: var(--muted); }
  .chips { display: flex; flex-wrap: wrap; gap: 8px; margin-top: 14px; }
  .chip { padding: 7px 12px; border: 1px solid var(--line); border-radius: 999px; background: var(--wash); font-size: 10px; font-weight: 700; color: #425066; }
  .section-title { display: flex; align-items: center; gap: 10px; margin: 22px 0 10px; }
  .section-title::before { content: ""; width: 34px; height: 4px; border-radius: 2px; background: var(--violet); }
  .benchmarks { display: grid; grid-template-columns: repeat(5, 1fr); gap: 8px; }
  .benchmark { border: 1px solid var(--line); border-radius: 7px; padding: 11px; min-height: 105px; }
  .benchmark strong { display: block; margin: 7px 0 4px; font-size: 16px; }
  .products { display: grid; grid-template-columns: 1fr 1fr; gap: 14px; }
  .product { border: 1px solid var(--line); border-radius: 8px; overflow: hidden; }
  .product-head { min-height: 68px; padding: 14px 16px; background: var(--lilac); }
  .product.crm .product-head { background: var(--ice); }
  .product-head p { margin-top: 3px; color: var(--muted); }
  table { width: 100%; border-collapse: collapse; }
  th { padding: 9px 10px; background: var(--wash); color: #526075; text-align: left; text-transform: uppercase; font-size: 8.5px; letter-spacing: .5px; }
  td { padding: 10px; vertical-align: top; border-top: 1px solid var(--line); }
  td strong { font-size: 12px; }
  .plan { width: 25%; }
  .price { width: 31%; font-weight: 800; color: var(--ink); }
  .setup { display: block; margin-top: 2px; color: var(--muted); font-weight: 400; }
  .notes { display: grid; grid-template-columns: repeat(3, 1fr); gap: 9px; margin-top: 12px; }
  .note { padding: 11px; background: var(--wash); border-radius: 7px; }
  .note p { margin-top: 4px; color: var(--muted); }
  .callout { margin-top: 12px; padding: 11px 14px; background: #fff4df; border-left: 5px solid var(--gold); border-radius: 0 7px 7px 0; }
  .formula { margin-top: 10px; padding: 11px; border-radius: 7px; background: var(--ink); color: white; text-align: center; font-weight: 800; font-size: 12px; }
  .two { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; }
  .panel { border: 1px solid var(--line); border-radius: 8px; padding: 14px; }
  .panel p { margin-top: 6px; color: var(--muted); }
  .agent-table th, .agent-table td { padding: 8px 10px; }
  .addons { display: grid; grid-template-columns: repeat(3, 1fr); gap: 9px; }
  .addon { border: 1px solid var(--line); border-radius: 7px; padding: 11px; min-height: 88px; }
  .addon strong { display: block; margin: 5px 0; color: var(--violet); font-size: 12px; }
  .bundles { display: grid; grid-template-columns: 1fr 1fr; gap: 10px; }
  .bundle { padding: 14px; border-radius: 8px; color: white; background: linear-gradient(115deg, #14213d, #27476e); }
  .bundle strong { display: block; margin: 4px 0; font-size: 20px; }
  .guardrails { columns: 2; column-gap: 28px; margin: 0; padding: 12px 16px 12px 30px; background: var(--rose); border: 1px solid #eccaca; border-radius: 8px; }
  .guardrails li { break-inside: avoid; margin-bottom: 6px; }
  .mechanics .section-title { margin: 14px 0 8px; }
  .mechanics .panel { padding: 11px; }
  .mechanics .addons { gap: 7px; }
  .mechanics .addon { min-height: 78px; padding: 8px; }
  .mechanics .bundle { padding: 11px; }
  .mechanics .guardrails { padding-top: 9px; padding-bottom: 9px; }
  .mechanics .guardrails li { margin-bottom: 4px; }
  .footer { position: absolute; left: 52px; right: 52px; bottom: 21px; display: flex; justify-content: space-between; align-items: end; border-top: 1px solid var(--line); padding-top: 8px; color: #687386; font-size: 8px; }
  .footer span:first-child { max-width: 610px; }
  .footer b { color: var(--ink); font-size: 9px; }
`;

const productTable = (name, description, cssClass, plans) => `
  <article class="product ${cssClass}">
    <header class="product-head"><h2>${name}</h2><p>${description}</p></header>
    <table>
      <thead><tr><th class="plan">Plan</th><th class="price">Subscription</th><th>Commercial envelope</th></tr></thead>
      <tbody>${plans.map((plan) => `<tr><td><strong>${plan.name}</strong><span class="setup">${plan.setup}</span></td><td class="price">${plan.price}</td><td>${plan.envelope}</td></tr>`).join("")}</tbody>
    </table>
  </article>`;

const footer = (sources, page) => `<div class="footer"><span>${sources}</span><b>${page}</b></div>`;

const html = `<!doctype html>
<html lang="en">
<head><meta charset="utf-8"><title>SignalLoop + eCRM Competitive Pricing Brief</title><style>${styles}</style></head>
<body>
  <section class="page">
    <div class="eyebrow">Commercial pricing brief · United States</div>
    <h1>Competitive entry. Governed scale.</h1>
    <p class="lead">SignalLoop executes governed multichannel engagement and AI-assisted prospecting. eCRM operates the lead-to-cash workflow. Both remain independently sellable.</p>
    <div class="chips"><span class="chip">Annual commitment · monthly billing</span><span class="chip">USD · taxes excluded</span><span class="chip">Provider usage and hosting separate</span><span class="chip">Research snapshot: 12 Sep 2026</span></div>

    <div class="section-title"><h2>AI sales and CRM reference points</h2></div>
    <div class="benchmarks">
      <div class="benchmark"><h3>AiSDR Solo</h3><strong>$250/mo</strong><p class="muted">1 user, 200 AI-researched contacts, 3 mailboxes; monthly.</p></div>
      <div class="benchmark"><h3>Agent Frank</h3><strong>$499/mo</strong><p class="muted">Salesforge autonomous agent; 2,000+ contacts; annual billing.</p></div>
      <div class="benchmark"><h3>Apollo</h3><strong>$49–$79</strong><p class="muted">Per seat/month annually; AI research and agentic loops use credits.</p></div>
      <div class="benchmark"><h3>Regie.ai Pro</h3><strong>$49/mo</strong><p class="muted">Single user, 5,000 monthly credits; agents included in workspace.</p></div>
      <div class="benchmark"><h3>HubSpot Sales</h3><strong>$20–$150</strong><p class="muted">Per seat/month; Professional is $100 plus $1,500 onboarding.</p></div>
    </div>

    <div class="section-title"><h2>Recommended competitive US launch list</h2></div>
    <div class="products">
      ${productTable("SignalLoop", "Email, voice, chat, sequences and governed agents", "", [
        { name: "Launch", setup: "Setup $750", price: "$199/mo", envelope: "3 users · 1 workspace · 5,000 active contacts · 1 production AI agent" },
        { name: "Scale", setup: "Setup $2,500", price: "$599/mo", envelope: "10 users · 25,000 active contacts · connector · 4 production AI agents" },
        { name: "Enterprise", setup: "Setup from $7,500", price: "From $1,499/mo", envelope: "Higher limits, SSO or dedicated operating requirements; quote after release review" },
      ])}
      ${productTable("eCRM", "Customer 360, pipeline, orders, production and finance", "crm", [
        { name: "Team Cell", setup: "Setup $2,000", price: "$399/mo", envelope: "10 users · dedicated customer cell · complete lead-to-cash workflow" },
        { name: "Business Cell", setup: "Setup $5,000", price: "$799/mo", envelope: "25 users · custom workflows · integration and reporting support" },
        { name: "Enterprise Cell", setup: "Setup from $10,000", price: "From $1,999/mo", envelope: "50 included users · managed cell or BYOC · negotiated terms" },
      ])}
    </div>
    <div class="notes">
      <div class="note"><h3>SignalLoop buyer math</h3><p>Launch sits below AiSDR Solo and includes three users, while keeping channel consumption visible.</p></div>
      <div class="note"><h3>eCRM buyer math</h3><p>Ten HubSpot Sales Professional seats are $1,000/month plus required onboarding.</p></div>
      <div class="note"><h3>Positioning</h3><p>Sell governed execution and workflow ownership, not an unlimited-volume AI SDR claim.</p></div>
    </div>
    <div class="callout"><strong>Recommended entry offer:</strong> SignalLoop Launch at $199/month and eCRM Team Cell at $399/month. Month-to-month is 15% higher. A 30-day paid pilot may be credited toward setup on annual conversion.</div>
    ${footer("Official sources: aisdr.com/pricing · salesforge.ai/pricing · apollo.io/pricing · regie.ai/pricing · legal.hubspot.com/hubspot-product-and-services-catalog. Reconfirm before quote issuance.", "01 / US")}
  </section>

  <section class="page">
    <div class="eyebrow">Commercial pricing brief · India</div>
    <h1>Localized for adoption. Priced for trust.</h1>
    <p class="lead">India pricing reflects local buyer economics while preserving tenant isolation, durable workflows, governed automation, and independent product boundaries.</p>
    <div class="chips"><span class="chip">Annual commitment · monthly billing</span><span class="chip">INR · GST excluded</span><span class="chip">Provider usage and hosting separate</span><span class="chip">No cross-subsidy between products</span></div>

    <div class="section-title"><h2>India and AI SDR reference points</h2></div>
    <div class="benchmarks">
      <div class="benchmark"><h3>Zoho CRM</h3><strong>₹800–₹2,600</strong><p class="muted">Per user/month annually, Standard through Ultimate.</p></div>
      <div class="benchmark"><h3>Kylas</h3><strong>₹12,999</strong><p class="muted">Approximate monthly flat-price CRM offer with unlimited users.</p></div>
      <div class="benchmark"><h3>AiSDR Solo</h3><strong>US $250</strong><p class="muted">Monthly AI SDR entry for one user and 200 researched contacts.</p></div>
      <div class="benchmark"><h3>Agent Frank</h3><strong>US $499</strong><p class="muted">Monthly autonomous-agent price on annual billing.</p></div>
      <div class="benchmark"><h3>HubSpot Sales</h3><strong>US $100</strong><p class="muted">Professional per seat/month plus onboarding and AI credits.</p></div>
    </div>

    <div class="section-title"><h2>Recommended competitive India launch list</h2></div>
    <div class="products">
      ${productTable("SignalLoop", "Governed engagement across email, voice and chat", "", [
        { name: "Launch", setup: "Setup ₹35,000", price: "₹9,900/mo", envelope: "3 users · 1 workspace · 5,000 active contacts · 1 production AI agent" },
        { name: "Scale", setup: "Setup ₹1,00,000", price: "₹29,900/mo", envelope: "10 users · 25,000 active contacts · connector · 4 production AI agents" },
        { name: "Enterprise", setup: "Setup from ₹3,00,000", price: "From ₹69,900/mo", envelope: "Higher limits or dedicated environment; quote after release review" },
      ])}
      ${productTable("eCRM", "A controlled customer cell from lead through collection", "crm", [
        { name: "Team Cell", setup: "Setup ₹1,00,000", price: "₹19,900/mo", envelope: "10 users · dedicated customer cell · lead-to-cash operating workflow" },
        { name: "Business Cell", setup: "Setup ₹2,00,000", price: "₹39,900/mo", envelope: "25 users · customization · integrations · reporting support" },
        { name: "Enterprise Cell", setup: "Setup from ₹4,00,000", price: "From ₹79,900/mo", envelope: "50 included users · managed cell or BYOC · negotiated terms" },
      ])}
    </div>
    <div class="notes">
      <div class="note"><h3>Where eCRM sits</h3><p>Ten Zoho Enterprise seats are ₹24,000/month; Team Cell is below that benchmark.</p></div>
      <div class="note"><h3>Why SignalLoop wins</h3><p>Launch is priced well below imported autonomous SDR offers before currency and provider spend.</p></div>
      <div class="note"><h3>Provider posture</h3><p>Tenant-owned approved provider accounts keep communication spend transparent.</p></div>
    </div>
    <div class="callout"><strong>Recommended entry offer:</strong> SignalLoop Launch at ₹9,900/month and eCRM Team Cell at ₹19,900/month. Use a paid pilot credited toward setup, not a permanent free tier.</div>
    ${footer("Official sources: zoho.com/crm/zohocrm-pricing.html · kylas.io/pricing · aisdr.com/pricing · salesforge.ai/pricing · legal.hubspot.com/hubspot-product-and-services-catalog. GST and consumption excluded.", "02 / INDIA")}
  </section>

  <section class="page mechanics">
    <div class="eyebrow">Commercial mechanics · AI agents, add-ons and guardrails</div>
    <h1>Price the job. Meter the consumption.</h1>
    <p class="lead">Bill published production workers with distinct jobs, permissions, knowledge, workflows and monitoring. Do not bill drafts, disabled agents, tests, language variants, voices or personas separately.</p>

    <div class="two" style="margin-top: 16px;">
      <div class="panel"><h2>Competitive hybrid model</h2><p>Include productive agent capacity in every SignalLoop tier, then charge for additional deployed workers. Keep model and channel consumption metered.</p><div class="formula">Platform + production agents + provider usage + support</div></div>
      <div class="panel"><h2>Market signal</h2><p>AiSDR starts at $250/month; Agent Frank is $499/month; HubSpot's prospecting agent consumes 100 credits per lead. SignalLoop should lead with transparent capacity, not hidden usage.</p></div>
    </div>

    <div class="section-title"><h2>Production-agent pricing</h2></div>
    <div class="two">
      <table class="agent-table"><thead><tr><th>United States</th><th>Price</th></tr></thead><tbody>
        <tr><td>Additional standard agent</td><td><strong>$49 Launch<br>$39 Scale</strong></td></tr>
        <tr><td>Autonomous revenue-agent entitlement</td><td><strong>$199/agent/mo</strong></td></tr>
        <tr><td>Voice/model/channel consumption</td><td>Customer account or prepaid wallet at actual cost + 15%</td></tr>
      </tbody></table>
      <table class="agent-table"><thead><tr><th>India</th><th>Price</th></tr></thead><tbody>
        <tr><td>Additional standard agent</td><td><strong>₹1,999 Launch<br>₹1,499 Scale</strong></td></tr>
        <tr><td>Autonomous revenue-agent entitlement</td><td><strong>₹9,990/agent/mo</strong></td></tr>
        <tr><td>Voice/model/channel consumption</td><td>Customer account or prepaid wallet at actual cost + 15%</td></tr>
      </tbody></table>
    </div>

    <div class="section-title"><h2>Recommended add-ons</h2></div>
    <div class="addons">
      <div class="addon"><h3>Additional human users</h3><strong>US $15 · India ₹749 / user / month</strong><p class="muted">Only above the included allowance.</p></div>
      <div class="addon"><h3>Managed provider operations</h3><strong>Actual usage + 15%</strong><p class="muted">Prepaid wallet, alerts and hard stops required.</p></div>
      <div class="addon"><h3>Additional CRM connector</h3><strong>US $99 · India ₹4,999 / month</strong><p class="muted">Custom engineering remains separately scoped.</p></div>
      <div class="addon"><h3>Managed customer cell</h3><strong>Hosting + 15% operations</strong><p class="muted">Defined monitoring and release operations.</p></div>
      <div class="addon"><h3>Premium support</h3><strong>12% of annual software fee</strong><p class="muted">24×7 requires a separately costed SLA.</p></div>
      <div class="addon"><h3>Implementation services</h3><strong>Fixed scope or day rate</strong><p class="muted">Migration, mapping, training and custom reports.</p></div>
    </div>

    <div class="section-title"><h2>Optional connected-product discount</h2></div>
    <div class="bundles">
      <div class="bundle"><h3>US Launch bundle</h3><strong>$539/month</strong><p>SignalLoop Launch + eCRM Team Cell · approximately 10% software-only discount</p></div>
      <div class="bundle"><h3>India Launch bundle</h3><strong>₹26,800/month</strong><p>SignalLoop Launch + eCRM Team Cell · approximately 10% software-only discount</p></div>
    </div>

    <div class="section-title"><h2>Commercial guardrails</h2></div>
    <ul class="guardrails">
      <li>Keep separate SKUs, entitlements, data boundaries and termination rights.</li>
      <li>Apply discounts only to recurring software, never setup, usage, cloud or services.</li>
      <li>Use annual commitments; month-to-month is 15% higher.</li>
      <li>Never promise unlimited voice, SMS, WhatsApp, email, storage, models or engineering.</li>
      <li>Publish Enterprise only as “from” until operating evidence supports firm limits.</li>
      <li>Review tenant gross margin monthly and adjust envelopes at renewal.</li>
    </ul>
    ${footer("Commercial recommendation, not a binding quotation. Final offers require current provider rates, taxes, support scope, hosting topology, data requirements and production-readiness review.", "03 / ADD-ONS")}
  </section>
</body>
</html>`;

await writeFile(path.join(outDir, htmlName), html, "utf8");

const browser = await chromium.launch();
try {
  const page = await browser.newPage();
  await page.goto(pathToFileURL(path.join(outDir, htmlName)).href, { waitUntil: "networkidle" });
  const layoutIssues = await page.evaluate(() => [...document.querySelectorAll(".page")].flatMap((pageElement, index) => {
    const footerElement = pageElement.querySelector(".footer");
    const contentBottom = Math.max(...[...pageElement.children]
      .filter((element) => element !== footerElement)
      .map((element) => element.getBoundingClientRect().bottom));
    const pageOverflow = pageElement.scrollHeight > pageElement.clientHeight;
    const footerOverlap = footerElement && contentBottom > footerElement.getBoundingClientRect().top;
    return pageOverflow || footerOverlap ? [`page ${index + 1}${pageOverflow ? " overflows" : ""}${footerOverlap ? " overlaps its footer" : ""}`] : [];
  }));
  if (layoutIssues.length > 0) {
    throw new Error(`Invalid print layout: ${layoutIssues.join(", ")}`);
  }
  await page.pdf({ path: path.join(outDir, pdfName), printBackground: true, preferCSSPageSize: true });
  await page.close();
} finally {
  await browser.close();
}

console.log(`Generated ${htmlName} and ${pdfName}.`);