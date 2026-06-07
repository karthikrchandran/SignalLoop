import { Bot, Headphones, User } from "lucide-react"

import { Badge } from "@/components/ui/badge"
import type { ChatbotThreadMessage } from "@/features/chatbot/api"
import { cn } from "@/lib/utils"

const senderIcon = {
  visitor: User,
  bot: Bot,
  agent: Headphones,
  system: Bot,
}

const senderLabel = {
  visitor: "Visitor",
  bot: "Bot",
  agent: "Agent",
  system: "System",
}

export function MessageBubble({ message }: { message: ChatbotThreadMessage }) {
  const Icon = senderIcon[message.sender]
  const isVisitor = message.sender === "visitor"
  const isAgent = message.sender === "agent"
  return (
    <div className={cn("flex gap-2", isVisitor ? "justify-start" : "justify-end")}>
      {isVisitor ? <Icon className="mt-2 size-4 shrink-0 text-muted-foreground" /> : null}
      <div
        className={cn(
          "max-w-[78%] rounded-lg border px-3 py-2 text-sm",
          isVisitor && "bg-background",
          message.sender === "bot" && "bg-muted",
          isAgent && "bg-primary text-primary-foreground",
        )}
      >
        <div className="mb-1 flex items-center gap-2">
          <span className="text-xs font-medium opacity-80">{senderLabel[message.sender]}</span>
          {message.sender === "bot" ? <Badge variant="secondary">AI</Badge> : null}
          {typeof message.bot_confidence === "number" ? (
            <span className="text-xs opacity-70">{Math.round(message.bot_confidence * 100)}%</span>
          ) : null}
        </div>
        <p className="whitespace-pre-wrap break-words">{message.content || ""}</p>
        <p className="mt-1 text-xs opacity-60">{new Date(message.created_at).toLocaleString()}</p>
      </div>
      {!isVisitor ? <Icon className="mt-2 size-4 shrink-0 text-muted-foreground" /> : null}
    </div>
  )
}

