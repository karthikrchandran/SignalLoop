import { expect, type Page } from "@playwright/test"

type UserMutationMethod = "POST" | "PATCH" | "DELETE"

function isUserMutationPath(pathname: string, method: UserMutationMethod) {
  if (method === "POST") {
    return pathname === "/api/v1/users/"
  }

  const match = /^\/api\/v1\/users\/([^/]+)$/.exec(pathname)
  return match?.[1] !== undefined && !["me", "signup"].includes(match[1])
}

export async function submitAndExpectUserMutation(
  page: Page,
  method: UserMutationMethod,
  trigger: () => Promise<unknown>,
) {
  const responsePromise = page.waitForResponse(
    (response) =>
      isUserMutationPath(new URL(response.url()).pathname, method) &&
      response.request().method() === method,
  )

  await trigger()
  const response = await responsePromise
  const responseText = response.ok() ? "" : await response.text()

  expect(
    response.ok(),
    `User ${method} mutation failed: status ${response.status()} ${response.statusText()}; response text: ${responseText}`,
  ).toBeTruthy()

  return response
}
