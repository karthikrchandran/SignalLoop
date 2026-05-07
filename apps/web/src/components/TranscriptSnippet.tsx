import { Quote } from "lucide-react"

interface TranscriptSnippetProps {
  excerpt: string
}

export function TranscriptSnippet({ excerpt }: TranscriptSnippetProps) {
  return (
    <div className="rounded-md border bg-muted/40 px-3 py-2">
      <div className="mb-1 flex items-center gap-1.5 text-xs font-medium text-muted-foreground">
        <Quote className="h-3.5 w-3.5" />
        Transcript excerpt
      </div>
      <p className="text-sm italic leading-6 text-foreground">{excerpt}</p>
    </div>
  )
}
