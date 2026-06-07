import { useState } from "react"
import { Send } from "lucide-react"

import { Button } from "@/components/ui/button"
import { Textarea } from "@/components/ui/textarea"

type ReplyComposerProps = {
  disabled?: boolean
  onSend: (message: string) => Promise<void>
}

export function ReplyComposer({ disabled, onSend }: ReplyComposerProps) {
  const [message, setMessage] = useState("")
  const [sending, setSending] = useState(false)

  const send = async () => {
    const trimmed = message.trim()
    if (!trimmed) return
    setSending(true)
    try {
      await onSend(trimmed)
      setMessage("")
    } finally {
      setSending(false)
    }
  }

  return (
    <div className="border-t p-3">
      <Textarea
        value={message}
        onChange={(event) => setMessage(event.target.value)}
        placeholder="Reply as agent"
        disabled={disabled || sending}
        className="min-h-20 resize-none"
      />
      <div className="mt-2 flex justify-end">
        <Button type="button" onClick={send} disabled={disabled || sending || !message.trim()} className="gap-2">
          <Send className="size-4" />
          Send
        </Button>
      </div>
    </div>
  )
}

