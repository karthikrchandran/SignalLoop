import { useState } from "react"
import { Bot, Send } from "lucide-react"

import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetFooter,
  SheetHeader,
  SheetTitle,
} from "@/components/ui/sheet"
import { Textarea } from "@/components/ui/textarea"
import {
  type ChatbotTestBotResponse,
  testChatbotQuestion,
} from "@/features/chatbot/api"

type TestBotSheetProps = {
  open: boolean
  onOpenChange: (open: boolean) => void
}

export function TestBotSheet({ open, onOpenChange }: TestBotSheetProps) {
  const [question, setQuestion] = useState("")
  const [response, setResponse] = useState<ChatbotTestBotResponse | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const ask = async () => {
    if (!question.trim()) return
    setLoading(true)
    setError(null)
    try {
      setResponse(await testChatbotQuestion(question.trim()))
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : "Failed to test bot")
    } finally {
      setLoading(false)
    }
  }

  return (
    <Sheet open={open} onOpenChange={onOpenChange}>
      <SheetContent className="w-full overflow-y-auto sm:max-w-xl">
        <SheetHeader>
          <SheetTitle className="flex items-center gap-2">
            <Bot className="size-5" />
            Test Bot
          </SheetTitle>
          <SheetDescription>Run a grounded answer against the current index.</SheetDescription>
        </SheetHeader>
        <div className="grid gap-4 px-4">
          <Textarea
            value={question}
            onChange={(event) => setQuestion(event.target.value)}
            rows={4}
            placeholder="Ask a question"
          />
          {error ? <div className="rounded-lg border border-destructive/40 bg-destructive/10 p-3 text-sm text-destructive">{error}</div> : null}
          {response ? (
            <div className="grid gap-4">
              <div className="rounded-lg border p-4">
                <div className="mb-2">
                  <Badge variant="secondary">{response.ai_disclosure}</Badge>
                </div>
                <p className="text-sm leading-6">{response.answer}</p>
              </div>
              <div className="grid gap-2">
                {response.sources.map((source) => (
                  <div key={source.chunk_id} className="rounded-lg border p-3 text-sm">
                    <div className="mb-1 flex items-center justify-between gap-2">
                      <span className="font-medium">{source.source_title}</span>
                      <Badge variant="outline">{source.score.toFixed(2)}</Badge>
                    </div>
                    <p className="text-muted-foreground">{source.excerpt}</p>
                  </div>
                ))}
              </div>
            </div>
          ) : null}
        </div>
        <SheetFooter>
          <Button onClick={ask} disabled={loading || !question.trim()} className="gap-2">
            <Send className="size-4" />
            {loading ? "Testing" : "Send"}
          </Button>
        </SheetFooter>
      </SheetContent>
    </Sheet>
  )
}
