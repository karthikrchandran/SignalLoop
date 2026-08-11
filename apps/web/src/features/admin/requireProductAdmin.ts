import { redirect } from "@tanstack/react-router"

import { type UserPublic, UsersService } from "@/client"
import { getSuiteContext } from "@/lib/signalloop-api"

export async function requireProductAdmin(capability: string) {
  const user = await UsersService.readUserMe()
  if ((user as UserPublic).is_superuser) {
    return
  }

  try {
    const suiteContext = await getSuiteContext()
    if (suiteContext.capabilities.includes(capability)) {
      return
    }
  } catch {
    // A product workspace is unavailable when the tenant capability cannot be resolved.
  }

  throw redirect({ to: "/" })
}
