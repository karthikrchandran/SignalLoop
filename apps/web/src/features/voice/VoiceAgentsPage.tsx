import { Mic2, Play, Square, Upload, User, Volume2, X } from "lucide-react"
import { useEffect, useRef, useState } from "react"

import { Alert } from "@/components/ui/alert"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card"
import { Label } from "@/components/ui/label"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"

type AgentId = "alex" | "morgan"

interface VoiceAgent {
  id: AgentId
  name: string
  gender: "Male" | "Female"
  accent: string
  tone: string
  description: string
  sampleScript: string
  /** Greeting spoken in the demo button */
  demoGreeting: string
  /** Preferred voice name hints (matched against SpeechSynthesis voices) */
  voiceHints: string[]
  /** Pitch tweak: >1 higher, <1 lower */
  pitch: number
  /** Rate tweak */
  rate: number
}

const AGENTS: VoiceAgent[] = [
  {
    id: "alex",
    name: "Alex",
    gender: "Male",
    accent: "Neutral (North American)",
    tone: "Professional & Authoritative",
    description:
      "Alex has a calm, confident delivery that works well for B2B outreach, appointment confirmations, and executive-level communications.",
    sampleScript:
      `Hi, this is Alex calling on behalf of {{company.name}}. I'm reaching out to schedule a brief 15-minute conversation with {{contact.firstName}} about {{campaign.topic}}. Is now a good time to talk?`,
    demoGreeting:
      "Good morning! My name is Alex, and I'm your dedicated outreach assistant. " +
      "I'm here to make every conversation count. " +
      "Could I start by getting your name? And how can I be of help to you today?",
    voiceHints: ["david", "alex", "daniel", "mark", "male", "en-us"],
    pitch: 0.9,
    rate: 0.95,
  },
  {
    id: "morgan",
    name: "Morgan",
    gender: "Female",
    accent: "Neutral (North American)",
    tone: "Empathetic & Conversational",
    description:
      "Morgan's warm, empathetic voice is ideal for customer re-engagement, follow-ups, support check-ins, and relationship-driven outreach.",
    sampleScript:
      `Hi {{contact.firstName}}, this is Morgan from {{company.name}}. I'm calling because we noticed it's been a while, and we'd love to reconnect. We have something special we think you'll find valuable — do you have just a moment?`,
    demoGreeting:
      "Good morning! I'm Morgan, and I'm so glad we have a chance to connect. " +
      "I'm here to listen and to help in any way I can. " +
      "It would be lovely to know your name — and please, tell me, how can I be of help to you today?",
    voiceHints: ["samantha", "zira", "susan", "karen", "female", "en-us"],
    pitch: 1.1,
    rate: 0.92,
  },
]

const OBJECT_TYPES = [
  { value: "appointment-reminder", label: "Appointment Reminder" },
  { value: "follow-up", label: "Follow-up Call" },
  { value: "re-engagement", label: "Re-engagement" },
  { value: "product-intro", label: "Product Introduction" },
  { value: "feedback-survey", label: "Feedback / Survey" },
  { value: "custom", label: "Custom" },
]

// ── Speech helper ─────────────────────────────────────────────────────────────
function pickVoice(hints: string[], gender: "Male" | "Female"): SpeechSynthesisVoice | null {
  const voices = window.speechSynthesis.getVoices()
  if (!voices.length) return null
  const langVoices = voices.filter((v) => v.lang.startsWith("en"))
  for (const hint of hints) {
    const match = langVoices.find((v) => v.name.toLowerCase().includes(hint.toLowerCase()))
    if (match) return match
  }
  // Fallback: pick any English voice that vaguely matches gender via name heuristics
  const genderHints = gender === "Male"
    ? ["david", "mark", "james", "tom", "daniel"]
    : ["samantha", "susan", "zira", "karen", "victoria", "fiona"]
  for (const h of genderHints) {
    const match = langVoices.find((v) => v.name.toLowerCase().includes(h))
    if (match) return match
  }
  return langVoices[0] ?? null
}
// ─────────────────────────────────────────────────────────────────────────────

export default function VoiceAgentsPage() {
  const [selectedAgent, setSelectedAgent] = useState<AgentId>("alex")
  const [objective, setObjective] = useState("appointment-reminder")
  const [scripts, setScripts] = useState<Record<AgentId, string>>({
    alex: AGENTS[0].sampleScript,
    morgan: AGENTS[1].sampleScript,
  })
  // ── Shared knowledgebase ──────────────────────────────────────────────────
  const [kbFiles, setKbFiles] = useState<File[]>([])
  const [kbSaved, setKbSaved] = useState(false)
  // ── Demo speech state ─────────────────────────────────────────────────────
  const [speakingAgent, setSpeakingAgent] = useState<AgentId | null>(null)
  const [voicesReady, setVoicesReady] = useState(false)
  // ─────────────────────────────────────────────────────────────────────────
  const [testStatus, setTestStatus] = useState<string | null>(null)
  const fileRef = useRef<HTMLInputElement>(null)

  // SpeechSynthesis voices load asynchronously in some browsers
  useEffect(() => {
    const load = () => setVoicesReady(window.speechSynthesis.getVoices().length > 0)
    load()
    window.speechSynthesis.addEventListener("voiceschanged", load)
    return () => window.speechSynthesis.removeEventListener("voiceschanged", load)
  }, [])

  const agent = AGENTS.find((a) => a.id === selectedAgent)!
  const script = scripts[selectedAgent]

  const handleScriptChange = (value: string) => {
    setScripts((prev) => ({ ...prev, [selectedAgent]: value }))
  }

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const newFiles = Array.from(e.target.files ?? [])
    setKbFiles((prev) => {
      const existing = new Set(prev.map((f) => f.name))
      return [...prev, ...newFiles.filter((f) => !existing.has(f.name))]
    })
    setKbSaved(false)
    // reset input so the same file can be re-added after remove
    e.target.value = ""
  }

  const removeKbFile = (name: string) => {
    setKbFiles((prev) => prev.filter((f) => f.name !== name))
    setKbSaved(false)
  }

  const saveKnowledgebase = () => {
    // In production this would POST to API; here we just confirm
    setKbSaved(true)
  }

  const handleTestCall = () => {
    setTestStatus(
      `Test call initiated using ${agent.name}. In integration mode, this will trigger a real preview call to your verified number.`,
    )
    setTimeout(() => setTestStatus(null), 6000)
  }

  const handleDemo = (a: VoiceAgent) => {
    // Stop any current speech
    window.speechSynthesis.cancel()
    if (speakingAgent === a.id) {
      setSpeakingAgent(null)
      return
    }
    const utterance = new SpeechSynthesisUtterance(a.demoGreeting)
    const voice = pickVoice(a.voiceHints, a.gender)
    if (voice) utterance.voice = voice
    utterance.pitch = a.pitch
    utterance.rate = a.rate
    utterance.onstart = () => setSpeakingAgent(a.id)
    utterance.onend = () => setSpeakingAgent(null)
    utterance.onerror = () => setSpeakingAgent(null)
    window.speechSynthesis.speak(utterance)
  }

  return (
    <div className="flex flex-col gap-6">
      <div>
        <h1 className="text-3xl font-semibold tracking-tight flex items-center gap-2">
          <Mic2 className="h-7 w-7 text-primary" />
          Voice Agents
        </h1>
        <p className="mt-1 text-sm text-muted-foreground">
          Choose an AI voice agent, write a script, and manage a shared
          knowledgebase for context-aware calls.
        </p>
      </div>

      {/* Agent selector */}
      <div className="grid md:grid-cols-2 gap-4">
        {AGENTS.map((a) => (
          <div
            key={a.id}
            onClick={() => setSelectedAgent(a.id)}
            className={`relative text-left rounded-xl border p-5 transition-all cursor-pointer ${
              selectedAgent === a.id
                ? "border-primary bg-primary/5 shadow-sm"
                : "border-border/70 hover:border-primary/50"
            }`}
          >
            <div className="flex items-center gap-3 mb-2">
              <div className={`flex h-10 w-10 items-center justify-center rounded-full text-primary ${speakingAgent === a.id ? "bg-primary/30 animate-pulse" : "bg-primary/10"}`}>
                <User className="h-5 w-5" />
              </div>
              <div className="flex-1 min-w-0">
                <p className="font-semibold text-base">{a.name}</p>
                <div className="flex gap-2 mt-0.5 flex-wrap">
                  <Badge variant="secondary" className="text-xs">{a.gender}</Badge>
                  <Badge variant="outline" className="text-xs">{a.tone}</Badge>
                </div>
              </div>
              {/* Demo button */}
              <Button
                size="sm"
                variant={speakingAgent === a.id ? "default" : "outline"}
                className="gap-1.5 shrink-0"
                onClick={(e) => {
                  e.stopPropagation()
                  handleDemo(a)
                }}
                title={speakingAgent === a.id ? "Stop demo" : `Hear ${a.name}`}
              >
                {speakingAgent === a.id ? (
                  <><Square className="h-3.5 w-3.5" /> Stop</>
                ) : (
                  <><Play className="h-3.5 w-3.5" /> Demo</>
                )}
              </Button>
            </div>
            <p className="text-xs text-muted-foreground leading-relaxed">{a.description}</p>
            <p className="mt-2 text-xs text-muted-foreground">
              <span className="font-medium text-foreground">Accent:</span> {a.accent}
            </p>
            {!voicesReady && (
              <p className="mt-1 text-xs text-amber-500">Loading speech voices…</p>
            )}
          </div>
        ))}
      </div>

      {/* Configuration tabs */}
      <Tabs defaultValue="script" className="mt-2">
        <TabsList>
          <TabsTrigger value="script">Script</TabsTrigger>
          <TabsTrigger value="knowledgebase">
            Knowledgebase
            {kbFiles.length > 0 && (
              <Badge variant="secondary" className="ml-2 text-xs">{kbFiles.length}</Badge>
            )}
          </TabsTrigger>
          <TabsTrigger value="settings">Call Settings</TabsTrigger>
        </TabsList>

        {/* ── Script tab ──────────────────────────────────────────────── */}
        <TabsContent value="script" className="mt-4 space-y-4">
          <Card>
            <CardHeader className="pb-3">
              <CardTitle className="text-base">
                {agent.name}&apos;s Call Script
              </CardTitle>
              <CardDescription>
                Use{" "}
                <code className="text-xs bg-muted px-1 rounded">
                  {"{{contact.firstName}}"}
                </code>{" "}
                and other tokens for personalisation. The agent reads this
                verbatim and falls back to the shared knowledgebase for
                follow-up questions.
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-3">
              <div className="space-y-1">
                <Label>Call Objective</Label>
                <Select value={objective} onValueChange={setObjective}>
                  <SelectTrigger>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    {OBJECT_TYPES.map((o) => (
                      <SelectItem key={o.value} value={o.value}>
                        {o.label}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
              <div className="space-y-1">
                <Label>Script</Label>
                <textarea
                  rows={8}
                  value={script}
                  onChange={(e: React.ChangeEvent<HTMLTextAreaElement>) =>
                    handleScriptChange(e.target.value)
                  }
                  placeholder="Enter the call script…"
                  className="flex min-h-[80px] w-full rounded-md border border-input bg-background px-3 py-2 font-mono text-sm ring-offset-background placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 resize-y"
                />
              </div>
              <Button
                onClick={handleTestCall}
                variant="outline"
                className="gap-2"
              >
                <Volume2 className="h-4 w-4" />
                Preview Test Call
              </Button>
              {testStatus && (
                <Alert className="text-sm">{testStatus}</Alert>
              )}
            </CardContent>
          </Card>
        </TabsContent>

        {/* ── Shared Knowledgebase tab ─────────────────────────────────── */}
        <TabsContent value="knowledgebase" className="mt-4">
          <Card>
            <CardHeader className="pb-3">
              <CardTitle className="text-base">Shared Knowledgebase</CardTitle>
              <CardDescription>
                These files are available to{" "}
                <strong>both Alex and Morgan</strong>. The agents reference
                them when a contact asks questions outside the script. Upload
                PDFs, DOCX, or TXT files.
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              {/* Uploaded file list */}
              {kbFiles.length > 0 && (
                <ul className="space-y-2">
                  {kbFiles.map((f) => (
                    <li
                      key={f.name}
                      className="flex items-center justify-between rounded-md border border-border/70 px-3 py-2 text-sm"
                    >
                      <span className="truncate text-muted-foreground">
                        {f.name}{" "}
                        <span className="text-xs">
                          ({(f.size / 1024).toFixed(0)} KB)
                        </span>
                      </span>
                      <button
                        onClick={() => removeKbFile(f.name)}
                        className="ml-3 shrink-0 text-muted-foreground hover:text-destructive transition-colors"
                        title="Remove"
                      >
                        <X className="h-4 w-4" />
                      </button>
                    </li>
                  ))}
                </ul>
              )}

              {/* Drop zone / add more */}
              <div
                className="flex flex-col items-center justify-center gap-3 rounded-lg border-2 border-dashed border-border/70 p-8 text-center cursor-pointer hover:border-primary/50 transition-colors"
                onClick={() => fileRef.current?.click()}
              >
                <Upload className="h-7 w-7 text-muted-foreground" />
                <p className="text-sm text-muted-foreground">
                  {kbFiles.length === 0
                    ? "Click to upload or drag & drop PDF, DOCX or TXT files"
                    : "Click to add more files"}
                </p>
                <p className="text-xs text-muted-foreground">Max 20 MB per file</p>
                <input
                  ref={fileRef}
                  type="file"
                  multiple
                  accept=".pdf,.docx,.txt,application/pdf,application/vnd.openxmlformats-officedocument.wordprocessingml.document,text/plain"
                  className="hidden"
                  onChange={handleFileChange}
                />
              </div>

              {kbSaved && (
                <p className="text-sm text-green-600 dark:text-green-400">
                  ✓ Knowledgebase saved — available to Alex and Morgan.
                </p>
              )}

              <Button
                disabled={kbFiles.length === 0}
                className="w-full"
                onClick={saveKnowledgebase}
              >
                Save Knowledgebase ({kbFiles.length} file
                {kbFiles.length !== 1 ? "s" : ""})
              </Button>
            </CardContent>
          </Card>
        </TabsContent>

        {/* ── Call Settings tab ────────────────────────────────────────── */}
        <TabsContent value="settings" className="mt-4">
          <Card>
            <CardHeader className="pb-3">
              <CardTitle className="text-base">Call Settings</CardTitle>
              <CardDescription>
                Configure retry attempts, call windows, and voicemail behaviour.
              </CardDescription>
            </CardHeader>
            <CardContent>
              <p className="text-sm text-muted-foreground">
                Advanced call configuration (retry count, time windows,
                voicemail recording, consent recording, DNC list integration)
                will be available once your telephony provider is connected in
                Settings.
              </p>
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>
    </div>
  )
}
