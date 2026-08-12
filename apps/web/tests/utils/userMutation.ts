import { expect, type Page } from "@playwright/test"

export async function submitAndExpectUserMutation(
  page: Page,
  method: string,
  trigger: () => Promise<unknown>,
) {
  const responsePromise = page.waitForResponse(
    (response) =>
      response.url().includes("/api/v1/users") &&
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
