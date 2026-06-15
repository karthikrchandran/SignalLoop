import { createFileRoute } from "@tanstack/react-router"
import { z } from "zod"

import ContactManagementPage from "@/features/contacts/ContactManagementPage"
import ContactTimelinePage from "@/features/contacts/ContactTimelinePage"

const contactsSearchSchema = z.object({
  contactId: z.string().optional(),
  campaignId: z.string().optional(),
  contactName: z.string().optional(),
})

export const Route = createFileRoute("/_layout/contacts")({
  validateSearch: contactsSearchSchema,
  head: () => ({
    meta: [{ title: "Contacts - SignalLoop" }],
  }),
  component: ContactsPage,
})

function ContactsPage() {
  const { contactId, campaignId, contactName } = Route.useSearch()

  if (!contactId) {
    return <ContactManagementPage />
  }

  return (
    <ContactTimelinePage
      contactId={contactId}
      campaignId={campaignId}
      contactName={contactName}
    />
  )
}
