import { createFileRoute } from "@tanstack/react-router"
import { z } from "zod"

import ContactTimelinePage from "@/features/contacts/ContactTimelinePage"

const contactsSearchSchema = z.object({
  contactId: z.string().optional(),
  campaignId: z.string().optional(),
  contactName: z.string().optional(),
})

export const Route = createFileRoute("/_layout/contacts")({
  validateSearch: contactsSearchSchema,
  head: () => ({
    meta: [{ title: "Contacts - EngageHub" }],
  }),
  component: ContactsPage,
})

function ContactsPage() {
  const { contactId, campaignId, contactName } = Route.useSearch()

  if (!contactId) {
    return (
      <div className="flex h-full items-center justify-center p-8">
        <p className="text-sm text-muted-foreground">
          Select a contact from a campaign to view their timeline.
        </p>
      </div>
    )
  }

  return (
    <ContactTimelinePage
      contactId={contactId}
      campaignId={campaignId}
      contactName={contactName}
    />
  )
}
