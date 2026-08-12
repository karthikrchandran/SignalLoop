import { expect, test } from "@playwright/test"
import { firstSuperuser, firstSuperuserPassword } from "./config.ts"
import { createUser } from "./utils/privateApi"
import { randomEmail, randomPassword } from "./utils/random"
import { logInUser, logOutUser } from "./utils/user"
import { submitAndExpectUserMutation } from "./utils/userMutation"

test("User mutation helper reports a failed response status and text", async ({ page }) => {
  await page.goto("/")

  await page.route("**/api/v1/users/", async (route) => {
    await route.fulfill({ status: 503, body: "test failure response" })
  })

  await expect(
    submitAndExpectUserMutation(page, "POST", () =>
      page.evaluate(() => fetch("/api/v1/users/", { method: "POST" })),
    ),
  ).rejects.toThrow(/status 503.*test failure response/)
})

test("User mutation helper ignores /users/me before an exact create response", async ({
  page,
}) => {
  await page.goto("/")

  await page.route("**/api/v1/users/me", async (route) => {
    await route.fulfill({ status: 200, body: "current user" })
  })
  await page.route("**/api/v1/users/", async (route) => {
    await route.fulfill({ status: 201, body: "created user" })
  })

  const response = await submitAndExpectUserMutation(page, "POST", () =>
    page.evaluate(async () => {
      await fetch("/api/v1/users/me", { method: "POST" })
      await fetch("/api/v1/users/", { method: "POST" })
    }),
  )

  expect(new URL(response.url()).pathname).toBe("/api/v1/users/")
})

test("User mutation helper matches exact update and delete endpoints", async ({
  page,
}) => {
  await page.goto("/")

  await page.route("**/api/v1/users/user-123", async (route) => {
    await route.fulfill({ status: 200, body: "updated user" })
  })

  for (const method of ["PATCH", "DELETE"] as const) {
    const response = await submitAndExpectUserMutation(page, method, () =>
      page.evaluate((requestMethod) =>
        fetch("/api/v1/users/user-123", { method: requestMethod }),
      method),
    )

    expect(new URL(response.url()).pathname).toBe("/api/v1/users/user-123")
  }
})

test("User mutation helper ignores /users/signup before exact update and delete responses", async ({
  page,
}) => {
  await page.goto("/")

  await page.route("**/api/v1/users/signup", async (route) => {
    await route.fulfill({ status: 200, body: "signup response" })
  })
  await page.route("**/api/v1/users/user-456", async (route) => {
    await route.fulfill({ status: 200, body: "user mutation response" })
  })

  for (const method of ["PATCH", "DELETE"] as const) {
    const response = await submitAndExpectUserMutation(page, method, () =>
      page.evaluate(async (requestMethod) => {
        await fetch("/api/v1/users/signup", { method: requestMethod })
        await fetch("/api/v1/users/user-456", { method: requestMethod })
      }, method),
    )

    expect(new URL(response.url()).pathname).toBe("/api/v1/users/user-456")
  }
})

test("Admin page is accessible and shows correct title", async ({ page }) => {
  await page.goto("/admin")
  await expect(
    page.getByRole("heading", { name: "Tenant administration" }),
  ).toBeVisible()
  await expect(page.getByRole("heading", { name: "Users" })).toBeVisible()
  await expect(
    page.getByText("Manage user accounts and permissions"),
  ).toBeVisible()
})

test("Add User button is visible", async ({ page }) => {
  await page.goto("/admin")
  await expect(page.getByRole("button", { name: "Add User" })).toBeVisible()
})

test.describe("Admin user management", () => {
  test("Create a new user successfully", async ({ page }) => {
    await page.goto("/admin")

    const email = randomEmail()
    const password = randomPassword()
    const fullName = "Test User Admin"

    await page.getByRole("button", { name: "Add User" }).click()

    await page.getByPlaceholder("Email").fill(email)
    await page.getByPlaceholder("Full name").fill(fullName)
    await page.getByPlaceholder("Password").first().fill(password)
    await page.getByPlaceholder("Password").last().fill(password)

    await submitAndExpectUserMutation(page, "POST", () =>
      page.getByRole("button", { name: "Save" }).click(),
    )

    await expect(page.getByText("User created successfully")).toBeVisible()

    await expect(page.getByRole("dialog")).not.toBeVisible()

    const userRow = page.getByRole("row").filter({ hasText: email })
    await expect(userRow).toBeVisible()

    await logOutUser(page)
    await page.getByTestId("email-input").fill(email)
    await page.getByTestId("password-input").fill(password)
    await page.getByRole("button", { name: "Log In" }).click()
    await page.waitForURL("/")
    await expect(page.getByTestId("user-menu")).toContainText(email)
  })

  test("Create a superuser", async ({ page }) => {
    await page.goto("/admin")

    const email = randomEmail()
    const password = randomPassword()

    await page.getByRole("button", { name: "Add User" }).click()

    await page.getByPlaceholder("Email").fill(email)
    await page.getByPlaceholder("Password").first().fill(password)
    await page.getByPlaceholder("Password").last().fill(password)
    await page.getByLabel("Is superuser?").check()
    await page.getByLabel("Is active?").check()

    await submitAndExpectUserMutation(page, "POST", () =>
      page.getByRole("button", { name: "Save" }).click(),
    )

    await expect(page.getByText("User created successfully")).toBeVisible()

    await expect(page.getByRole("dialog")).not.toBeVisible()

    const userRow = page.getByRole("row").filter({ hasText: email })
    await expect(userRow.getByText("Superuser")).toBeVisible()
  })

  test("Edit a user successfully", async ({ page }) => {
    await page.goto("/admin")

    const email = randomEmail()
    const password = randomPassword()
    const originalName = "Original Name"
    const updatedName = "Updated Name"

    await page.getByRole("button", { name: "Add User" }).click()
    await page.getByPlaceholder("Email").fill(email)
    await page.getByPlaceholder("Full name").fill(originalName)
    await page.getByPlaceholder("Password").first().fill(password)
    await page.getByPlaceholder("Password").last().fill(password)
    await submitAndExpectUserMutation(page, "POST", () =>
      page.getByRole("button", { name: "Save" }).click(),
    )

    await expect(page.getByText("User created successfully")).toBeVisible()
    await expect(page.getByRole("dialog")).not.toBeVisible()

    const userRow = page.getByRole("row").filter({ hasText: email })
    await userRow.getByRole("button").click()

    await page.getByRole("menuitem", { name: "Edit User" }).click()

    await page.getByPlaceholder("Full name").fill(updatedName)
    await submitAndExpectUserMutation(page, "PATCH", () =>
      page.getByRole("button", { name: "Save" }).click(),
    )

    await expect(page.getByText("User updated successfully")).toBeVisible()
    await expect(page.getByText(updatedName)).toBeVisible()
  })

  test("Delete a user successfully", async ({ page }) => {
    await page.goto("/admin")

    const email = randomEmail()
    const password = randomPassword()

    await page.getByRole("button", { name: "Add User" }).click()
    await page.getByPlaceholder("Email").fill(email)
    await page.getByPlaceholder("Password").first().fill(password)
    await page.getByPlaceholder("Password").last().fill(password)
    await submitAndExpectUserMutation(page, "POST", () =>
      page.getByRole("button", { name: "Save" }).click(),
    )

    await expect(page.getByText("User created successfully")).toBeVisible()

    await expect(page.getByRole("dialog")).not.toBeVisible()

    const userRow = page.getByRole("row").filter({ hasText: email })
    await userRow.getByRole("button").click()

    await page.getByRole("menuitem", { name: "Delete User" }).click()

    await submitAndExpectUserMutation(page, "DELETE", () =>
      page.getByRole("button", { name: "Delete" }).click(),
    )

    await expect(
      page.getByText("The user was deleted successfully"),
    ).toBeVisible()

    await expect(
      page.getByRole("row").filter({ hasText: email }),
    ).not.toBeVisible()
  })

  test("Cancel user creation", async ({ page }) => {
    await page.goto("/admin")

    await page.getByRole("button", { name: "Add User" }).click()
    await page.getByPlaceholder("Email").fill("test@example.com")

    await page.getByRole("button", { name: "Cancel" }).click()

    await expect(page.getByRole("dialog")).not.toBeVisible()
  })

  test("Email is required and must be valid", async ({ page }) => {
    await page.goto("/admin")

    await page.getByRole("button", { name: "Add User" }).click()

    await page.getByPlaceholder("Email").fill("invalid-email")
    await page.getByPlaceholder("Email").blur()

    await expect(page.getByText("Invalid email address")).toBeVisible()
  })

  test("Password must be at least 8 characters", async ({ page }) => {
    await page.goto("/admin")

    await page.getByRole("button", { name: "Add User" }).click()

    await page.getByPlaceholder("Email").fill(randomEmail())
    await page.getByPlaceholder("Password").first().fill("short")
    await page.getByPlaceholder("Password").last().fill("short")
    await page.getByRole("button", { name: "Save" }).click()

    await expect(
      page.getByText("Password must be at least 8 characters"),
    ).toBeVisible()
  })

  test("Passwords must match", async ({ page }) => {
    await page.goto("/admin")

    await page.getByRole("button", { name: "Add User" }).click()

    await page.getByPlaceholder("Email").fill(randomEmail())
    await page.getByPlaceholder("Password").first().fill(randomPassword())
    await page.getByPlaceholder("Password").last().fill("different12345")
    await page.getByPlaceholder("Password").last().blur()

    await expect(page.getByText("The passwords don't match")).toBeVisible()
  })
})

test.describe("Admin page access control", () => {
  test.use({ storageState: { cookies: [], origins: [] } })

  test("Non-superuser cannot access admin page", async ({ page }) => {
    const email = randomEmail()
    const password = randomPassword()

    await createUser({ email, password })
    await logInUser(page, email, password)

    await page.goto("/admin")

    await expect(page.getByRole("heading", { name: "Users" })).not.toBeVisible()
    await expect(page).toHaveURL(/\/$/)
    await expect(page.getByRole("heading", { name: "Revenue OS" })).toBeVisible()
  })

  test("Superuser can access admin page", async ({ page }) => {
    await logInUser(page, firstSuperuser, firstSuperuserPassword)

    await page.goto("/admin")

    await expect(
      page.getByRole("heading", { name: "Tenant administration" }),
    ).toBeVisible()
    await expect(page.getByRole("heading", { name: "Users" })).toBeVisible()
  })
})
