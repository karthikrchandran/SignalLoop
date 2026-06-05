import type { APIRequestContext } from "@playwright/test"

type Email = {
  id: string
  recipients: string[]
  subject: string
}

type MailpitAddress = {
  Address: string
  Name?: string
}

type MailpitMessage = {
  ID: string
  Subject: string
  To?: MailpitAddress[]
}

function getMailHost() {
  return (
    process.env.MAILPIT_HOST ||
    process.env.MAILCATCHER_HOST ||
    "http://localhost:8025"
  )
}

function normalizeMailpitAddress(address: MailpitAddress) {
  return address.Name
    ? `${address.Name} <${address.Address}>`
    : `<${address.Address}>`
}

async function findEmail({
  request,
  filter,
}: {
  request: APIRequestContext
  filter?: (email: Email) => boolean
}) {
  const host = getMailHost()
  const mailpitResponse = await request.get(`${host}/api/v1/messages`)

  if (mailpitResponse.ok()) {
    const payload = await mailpitResponse.json()
    let emails = ((payload.messages ?? []) as MailpitMessage[]).map(
      (message) => ({
        id: message.ID,
        recipients: (message.To ?? []).map(normalizeMailpitAddress),
        subject: message.Subject,
      }),
    )

    if (filter) {
      emails = emails.filter(filter)
    }

    return emails[0] ?? null
  }

  const response = await request.get(`${host}/messages`)

  let emails = await response.json()

  if (filter) {
    emails = emails.filter(filter)
  }

  const email = emails[emails.length - 1]

  if (email) {
    return email as Email
  }

  return null
}

export async function getEmailHtml({
  request,
  id,
}: {
  request: APIRequestContext
  id: string
}) {
  const host = getMailHost()
  const mailpitResponse = await request.get(`${host}/api/v1/message/${id}`)

  if (mailpitResponse.ok()) {
    const message = await mailpitResponse.json()
    return (message.HTML || message.Text || "") as string
  }

  const response = await request.get(`${host}/messages/${id}.html`)
  return response.text()
}

export function findLastEmail({
  request,
  filter,
  timeout = 5000,
}: {
  request: APIRequestContext
  filter?: (email: Email) => boolean
  timeout?: number
}) {
  const timeoutPromise = new Promise<never>((_, reject) =>
    setTimeout(
      () => reject(new Error("Timeout while trying to get latest email")),
      timeout,
    ),
  )

  const checkEmails = async () => {
    while (true) {
      const emailData = await findEmail({ request, filter })

      if (emailData) {
        return emailData
      }
      // Wait for 100ms before checking again
      await new Promise((resolve) => setTimeout(resolve, 100))
    }
  }

  return Promise.race([timeoutPromise, checkEmails()])
}
