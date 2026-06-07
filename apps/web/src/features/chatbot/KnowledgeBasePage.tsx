import { useEffect, useMemo, useState } from "react"
import { Bot, FileText, Globe2, HelpCircle, Plus, RefreshCw } from "lucide-react"

import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { Textarea } from "@/components/ui/textarea"
import {
  createKnowledgeSource,
  deleteKnowledgeSource,
  listKnowledgeSources,
  reindexAllKnowledgeSources,
  reindexKnowledgeSource,
  type ChatbotKnowledgeSource,
  uploadKnowledgeDocument,
} from "@/features/chatbot/api"
import { IndexingProgressBanner } from "@/features/chatbot/components/IndexingProgressBanner"
import { KnowledgeSourceRow } from "@/features/chatbot/components/KnowledgeSourceRow"
import { TestBotSheet } from "@/features/chatbot/components/TestBotSheet"

export default function KnowledgeBasePage() {
  const [sources, setSources] = useState<ChatbotKnowledgeSource[]>([])
  const [loading, setLoading] = useState(true)
  const [busyId, setBusyId] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [dismissed, setDismissed] = useState(false)
  const [testOpen, setTestOpen] = useState(false)
  const [urlTitle, setUrlTitle] = useState("")
  const [url, setUrl] = useState("")
  const [faqTitle, setFaqTitle] = useState("")
  const [faqContent, setFaqContent] = useState("")
  const [question, setQuestion] = useState("")
  const [answer, setAnswer] = useState("")
  const [file, setFile] = useState<File | null>(null)

  const readyCount = useMemo(() => sources.filter((source) => source.status === "ready").length, [sources])

  const loadSources = async () => {
    setLoading(true)
    setError(null)
    try {
      setSources((await listKnowledgeSources()).data)
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : "Failed to load knowledge sources")
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    void loadSources()
  }, [])

  const createWebsite = async () => {
    if (!url.trim()) return
    setBusyId("create-website")
    try {
      await createKnowledgeSource({
        source_type: "website",
        title: urlTitle.trim() || url.trim(),
        source_uri: url.trim(),
        crawl_depth: 1,
        max_pages: 10,
      })
      setUrl("")
      setUrlTitle("")
      await loadSources()
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : "Failed to add website")
    } finally {
      setBusyId(null)
    }
  }

  const createFaq = async () => {
    if (!faqContent.trim()) return
    setBusyId("create-faq")
    try {
      await createKnowledgeSource({
        source_type: "faq",
        title: faqTitle.trim() || "FAQ",
        content: faqContent.trim(),
      })
      setFaqTitle("")
      setFaqContent("")
      await loadSources()
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : "Failed to add FAQ")
    } finally {
      setBusyId(null)
    }
  }

  const createQa = async () => {
    if (!question.trim() || !answer.trim()) return
    setBusyId("create-qa")
    try {
      await createKnowledgeSource({
        source_type: "qa_pair",
        title: question.trim(),
        question: question.trim(),
        answer: answer.trim(),
      })
      setQuestion("")
      setAnswer("")
      await loadSources()
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : "Failed to add Q&A")
    } finally {
      setBusyId(null)
    }
  }

  const uploadDocument = async () => {
    if (!file) return
    setBusyId("upload-document")
    try {
      await uploadKnowledgeDocument(file)
      setFile(null)
      await loadSources()
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : "Failed to upload document")
    } finally {
      setBusyId(null)
    }
  }

  const reindex = async (sourceId: string) => {
    setBusyId(sourceId)
    try {
      await reindexKnowledgeSource(sourceId)
      await loadSources()
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : "Failed to re-index source")
    } finally {
      setBusyId(null)
    }
  }

  const reindexAll = async () => {
    setBusyId("all")
    try {
      await reindexAllKnowledgeSources()
      await loadSources()
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : "Failed to re-index")
    } finally {
      setBusyId(null)
    }
  }

  const removeSource = async (sourceId: string) => {
    setBusyId(sourceId)
    try {
      await deleteKnowledgeSource(sourceId)
      await loadSources()
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : "Failed to delete source")
    } finally {
      setBusyId(null)
    }
  }

  return (
    <div className="flex flex-col gap-6">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <p className="text-sm font-medium text-muted-foreground">Chatbot</p>
          <h1 className="flex items-center gap-2 text-2xl font-bold tracking-tight">
            <Bot className="size-6 text-muted-foreground" />
            Knowledge Base
          </h1>
        </div>
        <div className="flex gap-2">
          <Button variant="outline" size="sm" onClick={reindexAll} disabled={busyId === "all" || sources.length === 0} className="gap-2">
            <RefreshCw className={busyId === "all" ? "size-4 animate-spin" : "size-4"} />
            Re-index All
          </Button>
          <Button size="sm" onClick={() => setTestOpen(true)} disabled={readyCount === 0}>
            Test Bot
          </Button>
        </div>
      </div>

      <IndexingProgressBanner sources={sources} dismissed={dismissed} onDismiss={() => setDismissed(true)} />
      {error ? <div className="rounded-lg border border-destructive/40 bg-destructive/10 p-3 text-sm text-destructive">{error}</div> : null}

      <Tabs defaultValue="website">
        <TabsList>
          <TabsTrigger value="website" className="gap-2"><Globe2 className="size-4" />Website URLs</TabsTrigger>
          <TabsTrigger value="documents" className="gap-2"><FileText className="size-4" />Documents</TabsTrigger>
          <TabsTrigger value="faq" className="gap-2"><HelpCircle className="size-4" />FAQ/Q&A</TabsTrigger>
        </TabsList>
        <TabsContent value="website" className="rounded-lg border p-4">
          <div className="grid gap-3 md:grid-cols-[1fr_1.5fr_auto]">
            <div className="grid gap-2">
              <Label htmlFor="website-title">Title</Label>
              <Input id="website-title" value={urlTitle} onChange={(event) => setUrlTitle(event.target.value)} />
            </div>
            <div className="grid gap-2">
              <Label htmlFor="website-url">URL</Label>
              <Input id="website-url" value={url} onChange={(event) => setUrl(event.target.value)} />
            </div>
            <Button className="self-end gap-2" onClick={createWebsite} disabled={busyId === "create-website" || !url.trim()}>
              <Plus className="size-4" />
              Add
            </Button>
          </div>
        </TabsContent>
        <TabsContent value="documents" className="rounded-lg border p-4">
          <div className="grid gap-3 md:grid-cols-[1fr_auto]">
            <Input type="file" accept=".pdf,.docx,.txt" onChange={(event) => setFile(event.target.files?.[0] ?? null)} />
            <Button onClick={uploadDocument} disabled={busyId === "upload-document" || !file} className="gap-2">
              <Plus className="size-4" />
              Upload
            </Button>
          </div>
        </TabsContent>
        <TabsContent value="faq" className="rounded-lg border p-4">
          <div className="grid gap-4 lg:grid-cols-2">
            <div className="grid gap-3">
              <Input value={faqTitle} onChange={(event) => setFaqTitle(event.target.value)} placeholder="FAQ title" />
              <Textarea value={faqContent} onChange={(event) => setFaqContent(event.target.value)} rows={5} placeholder="FAQ or manual text" />
              <Button onClick={createFaq} disabled={busyId === "create-faq" || !faqContent.trim()} className="justify-self-start gap-2">
                <Plus className="size-4" />
                Add FAQ
              </Button>
            </div>
            <div className="grid gap-3">
              <Input value={question} onChange={(event) => setQuestion(event.target.value)} placeholder="Question" />
              <Textarea value={answer} onChange={(event) => setAnswer(event.target.value)} rows={5} placeholder="Answer" />
              <Button onClick={createQa} disabled={busyId === "create-qa" || !question.trim() || !answer.trim()} className="justify-self-start gap-2">
                <Plus className="size-4" />
                Add Q&A
              </Button>
            </div>
          </div>
        </TabsContent>
      </Tabs>

      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>Source</TableHead>
            <TableHead>Status</TableHead>
            <TableHead>Chunks</TableHead>
            <TableHead>Last Indexed</TableHead>
            <TableHead>Failure</TableHead>
            <TableHead className="text-right">Actions</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {sources.map((source) => (
            <KnowledgeSourceRow
              key={source.id}
              source={source}
              busy={busyId === source.id}
              onReindex={() => void reindex(source.id)}
              onDelete={() => void removeSource(source.id)}
            />
          ))}
          {!loading && sources.length === 0 ? (
            <TableRow>
              <TableCell colSpan={6} className="h-24 text-center text-muted-foreground">
                No knowledge sources
              </TableCell>
            </TableRow>
          ) : null}
        </TableBody>
      </Table>

      <TestBotSheet open={testOpen} onOpenChange={setTestOpen} />
    </div>
  )
}
