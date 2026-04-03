import { createFileRoute } from "@tanstack/react-router"
import OfferPackLibraryPage from "@/features/templates/OfferPackLibraryPage"

export const Route = createFileRoute("/_layout/offer-packs")({
  component: OfferPacksPage,
  head: () => ({
    meta: [
      {
        title: "Offer Packs - EngageHub",
      },
    ],
  }),
})

function OfferPacksPage() {
  return <OfferPackLibraryPage />
}
