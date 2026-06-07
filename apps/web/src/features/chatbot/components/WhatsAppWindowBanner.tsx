import { AlertTriangle } from "lucide-react"

export function WhatsAppWindowBanner() {
  return (
    <div className="border-t bg-amber-50 p-4 text-sm text-amber-950 dark:bg-amber-950/30 dark:text-amber-100">
      <div className="flex gap-3">
        <AlertTriangle className="mt-0.5 size-4 shrink-0" />
        <div>
          <p className="font-medium">WhatsApp 24-hour messaging window expired</p>
          <p className="mt-1 text-amber-900 dark:text-amber-100/80">
            The visitor must send a new message before an agent can reply through WhatsApp.
          </p>
        </div>
      </div>
    </div>
  )
}

