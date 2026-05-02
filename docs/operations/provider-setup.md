# Provider Setup — API Keys & Local Tools

All keys go into the `.env` file at the repo root.  
Start each section only when you're ready to use that feature.

---

## 1. Mailpit — Local Email Capture (already installed)

Mailpit intercepts all outgoing emails locally so nothing is sent to real inboxes during development.

**Status:** Already installed via Scoop.

**Start/Stop:** Managed automatically by `StartServer.ps1` / `StopServer.ps1`.

**Web UI:** http://localhost:8025  
**SMTP port:** 1025

`.env` settings (already set):
```
SMTP_HOST=localhost
SMTP_PORT=1025
SMTP_TLS=false
SMTP_USER=
SMTP_PASSWORD=
EMAILS_FROM_EMAIL=noreply@example.com
```

---

## 2. SendGrid — Transactional Email (production)

Used by the `sequence_worker` to send campaign emails to real contacts.

### Sign Up
1. Go to https://sendgrid.com → **Start for Free**
2. Verify your email address
3. Complete the sender identity verification (add a real "From" email you own)

### Get API Key
1. Dashboard → **Settings** → **API Keys** → **Create API Key**
2. Name it `engagehub-local`
3. Permission: **Restricted Access** → enable **Mail Send** only
4. Copy the key (shown only once)

### Configure Sender
1. Dashboard → **Settings** → **Sender Authentication**
2. Verify at minimum a single sender email address
3. Note that email address — it becomes `SENDGRID_FROM_EMAIL`

### Update `.env`
```
SENDGRID_API_KEY=SG.xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
SENDGRID_FROM_EMAIL=you@yourdomain.com
SENDGRID_WEBHOOK_SECRET=          # leave blank for now
```

**Free tier:** 100 emails/day forever.

---

## 3. Twilio — Outbound Voice Calls

Used by the `call_worker` to make AI-assisted outbound calls.

### Sign Up
1. Go to https://www.twilio.com → **Sign up**
2. Verify your phone number
3. Answer the onboarding questions: "Send messages" → "With code" → "Python"

### Get Credentials
1. Dashboard shows **Account SID** and **Auth Token** on the main page
2. Click **Get a Trial Number** → choose any US number → confirm

### Update `.env`
```
TWILIO_ACCOUNT_SID=ACxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
TWILIO_AUTH_TOKEN=xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
TWILIO_PHONE_NUMBER=+1xxxxxxxxxx
```

**Trial credit:** ~$15 USD free. Trial accounts can only call verified numbers until upgraded.  
**To verify a number (trial):** Console → Phone Numbers → Verified Caller IDs → Add.

---

## 4. Deepgram — Speech-to-Text & Text-to-Speech

Used by the `postcall_worker` to transcribe call recordings and by the call worker for TTS voice synthesis.

### Sign Up
1. Go to https://console.deepgram.com → **Sign Up**
2. No credit card required for trial

### Get API Key
1. Console → **API Keys** → **Create a New API Key**
2. Name it `engagehub-local`
3. Role: **Member** is sufficient
4. Copy the key

### Update `.env`
```
DEEPGRAM_API_KEY=xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
```

**Free credit:** $200 USD on signup (covers ~hundreds of hours of audio).

---

## 5. Groq — LLM Post-Call Processing

Used by the `postcall_worker` to summarize call transcripts and extract structured data using fast LLM inference.

### Sign Up
1. Go to https://console.groq.com → **Sign In with Google/GitHub** or create account
2. No credit card required

### Get API Key
1. Console → **API Keys** → **Create API Key**
2. Name it `engagehub-local`
3. Copy the key

### Update `.env`
```
GROQ_API_KEY=gsk_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
```

**Free tier:** Generous rate limits on Llama 3 / Mixtral models — sufficient for local dev.

---

## Verification Checklist

After filling in all keys, restart the API and workers (`StopApp.ps1` then `StartApp.ps1 -Workers`) and check the API logs for any provider errors on startup.

| Service    | `.env` key              | Test                                      |
|------------|-------------------------|-------------------------------------------|
| Mailpit    | *(no key needed)*       | http://localhost:8025 shows inbox         |
| SendGrid   | `SENDGRID_API_KEY`      | Send a test email via API → appears in SG activity |
| Twilio     | `TWILIO_ACCOUNT_SID`    | Make a test call to your verified number  |
| Deepgram   | `DEEPGRAM_API_KEY`      | Workers start without provider errors     |
| Groq       | `GROQ_API_KEY`          | Workers start without provider errors     |

---

## Security Note

Never commit `.env` to git. It is already listed in `.gitignore`.  
For production, use environment variables injected by your hosting platform — never a committed file.
