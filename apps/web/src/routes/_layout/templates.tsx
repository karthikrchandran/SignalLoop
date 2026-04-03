import { createFileRoute } from "@tanstack/react-router"
import TemplateLibraryPage from "@/features/templates/TemplateLibraryPage"

export const Route = createFileRoute("/_layout/templates")({
  component: TemplatesPage,
  head: () => ({
    meta: [
      {
        title: "Templates - EngageHub",
      },
    ],
  }),
})

function TemplatesPage() {
  return <TemplateLibraryPage />
}
