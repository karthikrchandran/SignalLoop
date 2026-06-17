import { Link } from "@tanstack/react-router"
import {
  Brain,
  Loader2,
  Mic2,
  Pencil,
  PhoneCall,
  Play,
  Plus,
  RefreshCw,
  Square,
  Trash2,
  TriangleAlert,
  User,
} from "lucide-react"
import { useCallback, useEffect, useMemo, useState } from "react"

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
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import { Textarea } from "@/components/ui/textarea"
import {
  listProspectingResearch,
  type ProspectingResearchResult,
} from "@/features/prospecting/api"
import { signalloopRequest } from "@/lib/signalloop-api"

type CampaignSummary = {
  id: string
  name: string
}

type CampaignsResponse = {
  data: CampaignSummary[]
}

type ScriptSummary = {
  id: string
  campaign_id: string
  name: string
  active: boolean
  created_at: string
}

type ScriptsResponse = {
  data: ScriptSummary[]
}

type ScriptParsed = {
  opening_pitch: string
  fallback_response: string
  scheduling_question: string
  qa_pairs: Array<{ question: string; answer: string }>
}

type ScriptDetail = ScriptSummary & {
  content: string
  parsed: ScriptParsed | null
}

type SetupIntegration = {
  key: string
  label: string
  configured: boolean
  source: string
  capability?: string | null
  provider?: string | null
  provider_label?: string | null
  note?: string | null
}

type SetupOverview = {
  callbacks: {
    public_host: boolean
    public_base_url: string
    twilio_twiml_url: string
    twilio_media_stream_url: string
  }
  integrations: SetupIntegration[]
}

type CallListItem = {
  call_request_id: string
  contact_id: string
  campaign_id: string
  status: string
  outcome: string | null
  duration_seconds: number | null
  scheduled_at: string | null
  created_at: string
}

type CallsResponse = {
  data: CallListItem[]
  count: number
}

type CallOutcomeIntelligence = {
  summary: string
  sentiment: string
  objection: string | null
  next_action: string
  recommended_follow_up: string
}

type CallDetail = CallListItem & {
  trigger_reason: string | null
  recording_url: string | null
  transcript: string | null
  unanswered_questions: string[] | null
  scheduling_interest: boolean | null
  intelligence: CallOutcomeIntelligence | null
}

type TestCallResponse = {
  call_request_id: string
  status: string
  message: string
}

type VoiceProfileId = "alex" | "morgan" | "rajesh" | "priya"

type VoiceLanguageId = "en-US" | "hi-IN"

type VoiceLanguage = {
  id: VoiceLanguageId
  label: string
}

type VoiceProfile = {
  id: VoiceProfileId
  name: string
  gender: "Male" | "Female"
  accent: string
  tone: string
  description: string
  demoGreetings: Record<VoiceLanguageId, string>
  voiceHints: Record<VoiceLanguageId, string[]>
  pitch: number
  rate: number
  languages?: VoiceLanguageId[]
  speechLanguageOverrides?: Partial<Record<VoiceLanguageId, string>>
}

const VOICE_LANGUAGES: VoiceLanguage[] = [
  { id: "en-US", label: "English" },
  { id: "hi-IN", label: "Hindi" },
]

const DEFAULT_VOICE_LANGUAGE = VOICE_LANGUAGES[0]

const VOICE_PROFILES: VoiceProfile[] = [
  {
    id: "alex",
    name: "Alex",
    gender: "Male",
    accent: "Neutral North American",
    tone: "Professional and authoritative",
    description:
      "Best for B2B outreach, appointment confirmations, and executive-level conversations.",
    demoGreetings: {
      "en-US":
        "Good morning. My name is Alex, and I am your outreach assistant. I am here to make every conversation count.",
      "hi-IN":
        "Namaste. Mera naam Alex hai, aur main aapka outreach assistant hoon.",
    },
    voiceHints: {
      "en-US": ["david", "alex", "daniel", "mark", "male", "en-us"],
      "hi-IN": ["hemant", "ravi", "google hindi", "hi-in", "india"],
    },
    pitch: 0.9,
    rate: 0.95,
    languages: ["en-US"],
  },
  {
    id: "morgan",
    name: "Morgan",
    gender: "Female",
    accent: "Neutral North American",
    tone: "Empathetic and conversational",
    description:
      "Best for customer re-engagement, follow-ups, support check-ins, and relationship-led outreach.",
    demoGreetings: {
      "en-US":
        "Good morning. I am Morgan, and I am glad we have a chance to connect. I am here to listen and help.",
      "hi-IN":
        "Namaste. Main Morgan hoon, aur mujhe aapse judkar khushi ho rahi hai.",
    },
    voiceHints: {
      "en-US": ["samantha", "zira", "susan", "karen", "female", "en-us"],
      "hi-IN": ["kalpana", "heera", "google hindi", "hi-in", "india"],
    },
    pitch: 1.1,
    rate: 0.92,
    languages: ["en-US"],
  },
  {
    id: "rajesh",
    name: "Rajesh",
    gender: "Male",
    accent: "Indian English / Hindi",
    tone: "Warm and confident",
    description:
      "Best for regional outreach, follow-ups, and appointment calls where Hindi support improves trust.",
    demoGreetings: {
      "en-US":
        "Good morning. My name is Rajesh, and I am calling to help you with the next step.",
      "hi-IN":
        "Namaste. Mera naam Rajesh hai, aur main aapki madad ke liye call kar raha hoon.",
    },
    voiceHints: {
      "en-US": ["prabhat", "ravi", "hemant", "narayanan", "india", "indian"],
      "hi-IN": ["hemant", "ravi", "prabhat", "google hindi", "india"],
    },
    pitch: 0.82,
    rate: 0.9,
    languages: ["en-US", "hi-IN"],
    speechLanguageOverrides: {
      "en-US": "en-IN",
      "hi-IN": "hi-IN",
    },
  },
  {
    id: "priya",
    name: "Priya",
    gender: "Female",
    accent: "Indian English / Hindi",
    tone: "Sweet and warm",
    description:
      "Best for Hindi-aware re-engagement, customer check-ins, and relationship-led follow-ups.",
    demoGreetings: {
      "en-US":
        "Hi! I am Priya, and I am so glad to connect with you today. Let me know how I can help.",
      "hi-IN":
        "Namaste! Main Priya hoon, aur aapse baat karke bahut khushi hui. Main aapki kaise madad kar sakti hoon?",
    },
    voiceHints: {
      "en-US": [
        "neerja",
        "kalpana",
        "swara",
        "ava",
        "emma",
        "mia",
        "jenny",
        "aria",
        "zira",
      ],
      "hi-IN": ["swara", "kalpana", "heera", "google hindi", "neerja"],
    },
    pitch: 1.08,
    rate: 0.92,
    speechLanguageOverrides: {
      "en-US": "en-IN",
      "hi-IN": "hi-IN",
    },
  },
]

const DEFAULT_VOICE_PROFILE = VOICE_PROFILES[0]

const scriptForProfile = (
  profile: VoiceProfile,
  language: VoiceLanguage = DEFAULT_VOICE_LANGUAGE,
) => {
  if (language.id === "hi-IN") {
    return [
      "## Opening Pitch",
      `Namaste {{first_name}}, main ${profile.name} hoon SignalLoop se aapke campaign ke baare mein call kar raha/rahi hoon.`,
      "",
      "## Q&A",
      "Q: Yeh call kis baare mein hai?",
      "A: Yeh ek chhota sa update hai aur agle steps confirm karne ke liye hai.",
      "",
      "## Fallback",
      "Main aapko email par aur jankari bhej sakta/sakti hoon.",
      "",
      "## Scheduling",
      "Ek chhoti follow-up call ke liye kaunsa samay theek rahega?",
    ].join("\n")
  }

  return [
    "## Opening Pitch",
    `Hi {{first_name}}, this is ${profile.name} from SignalLoop calling about your campaign.`,
    "",
    "## Q&A",
    "Q: What does this cover?",
    "A: A brief overview and next steps.",
    "",
    "## Fallback",
    "I can follow up with more detail by email.",
    "",
    "## Scheduling",
    "What time works best for a quick follow-up call?",
  ].join("\n")
}

const formatDate = (value: string) => new Date(value).toLocaleString()

const integrationDisplayName = (
  integration: SetupIntegration | undefined,
  fallback: string,
) => integration?.provider_label ?? integration?.label ?? fallback

function pickSpeechVoice(
  hints: string[],
  gender: VoiceProfile["gender"],
  languageId: string,
) {
  if (!("speechSynthesis" in window)) return null
  const voices = window.speechSynthesis.getVoices()
  if (!voices.length) return null
  const languageIdLower = languageId.toLowerCase()
  const languagePrefix = languageIdLower.split("-")[0]
  const exactLanguageVoices = voices.filter(
    (voice) => voice.lang.toLowerCase() === languageIdLower,
  )
  const languageFamilyVoices = voices.filter((voice) => {
    const lang = voice.lang.toLowerCase()
    return lang.startsWith(languagePrefix)
  })
  const fallbackVoices = voices.filter((voice) =>
    voice.lang.toLowerCase().startsWith("en"),
  )
  const candidateVoices = exactLanguageVoices.length
    ? exactLanguageVoices
    : languageFamilyVoices.length
      ? languageFamilyVoices
      : fallbackVoices
  for (const hint of hints) {
    const match = candidateVoices.find((voice) =>
      voice.name.toLowerCase().includes(hint.toLowerCase()),
    )
    if (match) return match
  }
  const fallbackHints =
    gender === "Male"
      ? ["hemant", "ravi", "david", "mark", "james", "tom", "daniel"]
      : [
          "kalpana",
          "heera",
          "samantha",
          "susan",
          "zira",
          "karen",
          "victoria",
          "fiona",
        ]
  for (const hint of fallbackHints) {
    const match = candidateVoices.find((voice) =>
      voice.name.toLowerCase().includes(hint),
    )
    if (match) return match
  }
  // Final gender-keyword pass — catches voices that include "male"/"female" in name
  // e.g. "Google UK English Male", "Google UK English Female"
  const genderKeyword = gender === "Male" ? "male" : "female"
  const genderVoices = candidateVoices.filter((voice) =>
    voice.name.toLowerCase().includes(genderKeyword),
  )
  if (genderVoices.length > 0) return genderVoices[0]
  // For non-English languages, keep a native voice even if gender is imperfect —
  // an Indian-accented Hindi voice with low pitch sounds far better than an
  // English voice trying to speak Hindi text
  if (!languageIdLower.startsWith("en") && candidateVoices.length > 0) {
    return candidateVoices[0]
  }
  // Cross-language gender rescue (English only) — prefer correctly-gendered
  // English voice over wrong-gender voice when language is English
  const englishGenderVoices = voices.filter(
    (voice) =>
      voice.lang.toLowerCase().startsWith("en") &&
      voice.name.toLowerCase().includes(genderKeyword),
  )
  if (englishGenderVoices.length > 0) return englishGenderVoices[0]
  // Absolute last resort — any candidate voice
  return candidateVoices[0] ?? voices[0] ?? null
}

export default function VoiceAgentsPage() {
  const [campaigns, setCampaigns] = useState<CampaignSummary[]>([])
  const [scripts, setScripts] = useState<ScriptSummary[]>([])
  const [callPrepSnapshots, setCallPrepSnapshots] = useState<
    ProspectingResearchResult[]
  >([])
  const [recentCalls, setRecentCalls] = useState<CallListItem[]>([])
  const [latestCallDetail, setLatestCallDetail] = useState<CallDetail | null>(
    null,
  )
  const [setupOverview, setSetupOverview] = useState<SetupOverview | null>(null)
  const [selectedCampaignId, setSelectedCampaignId] = useState("")
  const [selectedScriptId, setSelectedScriptId] = useState<string | null>(null)
  const [selectedScript, setSelectedScript] = useState<ScriptDetail | null>(
    null,
  )
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [testCallLoading, setTestCallLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [feedback, setFeedback] = useState<string | null>(null)
  const [dialogOpen, setDialogOpen] = useState(false)
  const [editorMode, setEditorMode] = useState<"create" | "edit">("create")
  const [scriptName, setScriptName] = useState("")
  const [editorCampaignId, setEditorCampaignId] = useState("")
  const [scriptContent, setScriptContent] = useState(
    scriptForProfile(DEFAULT_VOICE_PROFILE, DEFAULT_VOICE_LANGUAGE),
  )
  const [active, setActive] = useState(true)
  const [selectedVoiceProfileId, setSelectedVoiceProfileId] =
    useState<VoiceProfileId>(DEFAULT_VOICE_PROFILE.id)
  const [selectedVoiceLanguageId, setSelectedVoiceLanguageId] =
    useState<VoiceLanguageId>(DEFAULT_VOICE_LANGUAGE.id)

  const handleSelectVoiceProfile = (id: VoiceProfileId) => {
    setSelectedVoiceProfileId(id)
    const profile = VOICE_PROFILES.find((p) => p.id === id)
    if (
      profile?.languages &&
      !profile.languages.includes(selectedVoiceLanguageId)
    ) {
      setSelectedVoiceLanguageId(profile.languages[0])
    }
  }

  const [speakingProfileId, setSpeakingProfileId] =
    useState<VoiceProfileId | null>(null)
  const [voicesReady, setVoicesReady] = useState(false)

  const selectedVoiceProfile = useMemo(
    () =>
      VOICE_PROFILES.find((profile) => profile.id === selectedVoiceProfileId) ??
      DEFAULT_VOICE_PROFILE,
    [selectedVoiceProfileId],
  )

  const selectedVoiceLanguage = useMemo(
    () =>
      VOICE_LANGUAGES.find(
        (language) => language.id === selectedVoiceLanguageId,
      ) ?? DEFAULT_VOICE_LANGUAGE,
    [selectedVoiceLanguageId],
  )

  const filteredScripts = useMemo(
    () =>
      scripts.filter(
        (script) =>
          !selectedCampaignId || script.campaign_id === selectedCampaignId,
      ),
    [scripts, selectedCampaignId],
  )

  const findIntegration = (capability: string, legacyKeys: string[] = []) => {
    const integrations = setupOverview?.integrations ?? []
    return (
      integrations.find(
        (integration) =>
          integration.capability === capability ||
          integration.key === capability,
      ) ??
      integrations.find(
        (integration) =>
          !integration.capability && legacyKeys.includes(integration.key),
      )
    )
  }

  const voiceIntegration = findIntegration("voice", ["twilio", "vapi"])
  const sttIntegration = findIntegration("stt", ["deepgram"])
  const ttsIntegration = findIntegration("tts", ["deepgram"])
  const llmIntegration = findIntegration("llm", ["groq"])
  const voiceReadinessItems = [
    {
      label: integrationDisplayName(voiceIntegration, "Voice provider"),
      ready: voiceIntegration?.configured ?? false,
    },
    {
      label: integrationDisplayName(sttIntegration, "Speech-to-text"),
      ready: sttIntegration?.configured ?? false,
    },
    {
      label: integrationDisplayName(ttsIntegration, "Text-to-speech"),
      ready: ttsIntegration?.configured ?? false,
    },
    {
      label: integrationDisplayName(llmIntegration, "LLM provider"),
      ready: llmIntegration?.configured ?? false,
    },
    {
      label: "Public callbacks",
      ready: setupOverview?.callbacks.public_host ?? false,
    },
  ]
  const missingVoiceReadinessItems = voiceReadinessItems.filter(
    (item) => !item.ready,
  )
  const latestCallPrepSnapshot = callPrepSnapshots[0] ?? null
  const selectedVoiceProviderName = integrationDisplayName(
    voiceIntegration,
    "Voice provider",
  )
  const testCallDisabledReason = !selectedScript
    ? "Select a voice script."
    : !latestCallPrepSnapshot
      ? "Run prospecting research first."
      : missingVoiceReadinessItems.length > 0
        ? "Complete voice readiness setup."
        : null

  useEffect(() => {
    if (!("speechSynthesis" in window)) return
    const loadVoices = () =>
      setVoicesReady(window.speechSynthesis.getVoices().length > 0)
    loadVoices()
    window.speechSynthesis.addEventListener("voiceschanged", loadVoices)
    return () => {
      window.speechSynthesis.removeEventListener("voiceschanged", loadVoices)
      window.speechSynthesis.cancel()
    }
  }, [])

  const loadIndex = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const callPrepRequest = listProspectingResearch().catch(() => ({
        data: [],
        count: 0,
      }))
      const callsRequest = signalloopRequest<CallsResponse>(
        "/api/v1/calls/?limit=5",
      ).catch(() => ({
        data: [],
        count: 0,
      }))
      const [
        campaignResponse,
        scriptsResponse,
        overviewResponse,
        callPrepResponse,
        callsResponse,
      ] = await Promise.all([
        signalloopRequest<CampaignsResponse>("/api/v1/campaigns/"),
        signalloopRequest<ScriptsResponse>("/api/v1/scripts/"),
        signalloopRequest<SetupOverview>("/api/v1/utils/setup-overview/"),
        callPrepRequest,
        callsRequest,
      ])
      setCampaigns(campaignResponse.data)
      setScripts(scriptsResponse.data)
      setCallPrepSnapshots(callPrepResponse.data)
      setRecentCalls(callsResponse.data)
      setSetupOverview(overviewResponse)
      setSelectedCampaignId(
        (current) => current || campaignResponse.data[0]?.id || "",
      )
      setSelectedScriptId((current) => {
        if (
          current &&
          scriptsResponse.data.some((script) => script.id === current)
        ) {
          return current
        }
        const nextScript = scriptsResponse.data.find(
          (script) =>
            !selectedCampaignId || script.campaign_id === selectedCampaignId,
        )
        return nextScript?.id ?? scriptsResponse.data[0]?.id ?? null
      })
      if (!editorCampaignId && campaignResponse.data[0]) {
        setEditorCampaignId(campaignResponse.data[0].id)
      }
      const latestCall = callsResponse.data[0]
      if (latestCall) {
        try {
          const detail = await signalloopRequest<CallDetail>(
            `/api/v1/calls/${latestCall.call_request_id}`,
          )
          setLatestCallDetail(detail)
        } catch {
          setLatestCallDetail(null)
        }
      } else {
        setLatestCallDetail(null)
      }
    } catch (requestError) {
      setError(
        requestError instanceof Error
          ? requestError.message
          : "Failed to load voice setup",
      )
    } finally {
      setLoading(false)
    }
  }, [editorCampaignId, selectedCampaignId])

  const loadScriptDetail = useCallback(async (scriptId: string) => {
    try {
      const detail = await signalloopRequest<ScriptDetail>(
        `/api/v1/scripts/${scriptId}`,
      )
      setSelectedScript(detail)
    } catch (requestError) {
      setSelectedScript(null)
      setError(
        requestError instanceof Error
          ? requestError.message
          : "Failed to load script details",
      )
    }
  }, [])

  useEffect(() => {
    void loadIndex()
  }, [loadIndex])

  useEffect(() => {
    if (!selectedScriptId) {
      setSelectedScript(null)
      return
    }
    void loadScriptDetail(selectedScriptId)
  }, [selectedScriptId, loadScriptDetail])

  useEffect(() => {
    if (!selectedCampaignId) {
      return
    }
    if (filteredScripts.length === 0) {
      setSelectedScriptId(null)
      return
    }
    if (
      !selectedScriptId ||
      !filteredScripts.some((script) => script.id === selectedScriptId)
    ) {
      setSelectedScriptId(filteredScripts[0].id)
    }
  }, [filteredScripts, selectedCampaignId, selectedScriptId])

  const openCreateDialog = () => {
    setEditorMode("create")
    setScriptName(
      `${selectedVoiceProfile.name} ${selectedVoiceLanguage.label} campaign script`,
    )
    setEditorCampaignId(selectedCampaignId || campaigns[0]?.id || "")
    setScriptContent(
      scriptForProfile(selectedVoiceProfile, selectedVoiceLanguage),
    )
    setActive(true)
    setDialogOpen(true)
  }

  const previewVoiceProfile = (profile: VoiceProfile) => {
    if (!("speechSynthesis" in window)) {
      setFeedback("Browser voice preview is not available in this environment.")
      return
    }

    window.speechSynthesis.cancel()
    if (speakingProfileId === profile.id) {
      setSpeakingProfileId(null)
      return
    }

    const utterance = new SpeechSynthesisUtterance(
      profile.demoGreetings[selectedVoiceLanguage.id],
    )
    const speechLanguageId =
      profile.speechLanguageOverrides?.[selectedVoiceLanguage.id] ??
      selectedVoiceLanguage.id
    const speechVoice = pickSpeechVoice(
      profile.voiceHints[selectedVoiceLanguage.id],
      profile.gender,
      speechLanguageId,
    )
    if (speechVoice) utterance.voice = speechVoice
    utterance.lang = speechLanguageId
    utterance.pitch = profile.pitch
    utterance.rate = profile.rate
    utterance.onstart = () => setSpeakingProfileId(profile.id)
    utterance.onend = () => setSpeakingProfileId(null)
    utterance.onerror = () => setSpeakingProfileId(null)
    window.speechSynthesis.speak(utterance)
  }

  const openEditDialog = () => {
    if (!selectedScript) {
      return
    }
    setEditorMode("edit")
    setScriptName(selectedScript.name)
    setEditorCampaignId(selectedScript.campaign_id)
    setScriptContent(selectedScript.content)
    setActive(selectedScript.active)
    setDialogOpen(true)
  }

  const saveScript = async () => {
    if (!scriptName.trim() || !editorCampaignId || !scriptContent.trim()) {
      setError("Script name, campaign, and content are required.")
      return
    }

    setSaving(true)
    setError(null)
    setFeedback(null)
    try {
      let scriptId = selectedScript?.id
      if (editorMode === "create") {
        const created = await signalloopRequest<ScriptSummary>(
          "/api/v1/scripts/",
          {
            method: "POST",
            idempotent: true,
            body: {
              name: scriptName.trim(),
              campaign_id: editorCampaignId,
              content: scriptContent.trim(),
            },
          },
        )
        scriptId = created.id
      } else if (scriptId) {
        await signalloopRequest<ScriptDetail>(`/api/v1/scripts/${scriptId}`, {
          method: "PUT",
          idempotent: true,
          body: {
            name: scriptName.trim(),
            content: scriptContent.trim(),
            active,
          },
        })
      }

      if (!scriptId) {
        throw new Error("Script id was not returned by the API.")
      }

      await loadIndex()
      setSelectedCampaignId(editorCampaignId)
      setSelectedScriptId(scriptId)
      setFeedback(
        editorMode === "create" ? "Script created." : "Script updated.",
      )
      setDialogOpen(false)
    } catch (requestError) {
      setError(
        requestError instanceof Error
          ? requestError.message
          : "Could not save script",
      )
    } finally {
      setSaving(false)
    }
  }

  const deleteSelectedScript = async () => {
    if (!selectedScript) {
      return
    }
    setSaving(true)
    setError(null)
    setFeedback(null)
    try {
      await signalloopRequest(`/api/v1/scripts/${selectedScript.id}`, {
        method: "DELETE",
        idempotent: true,
      })
      const deletedId = selectedScript.id
      await loadIndex()
      setSelectedScriptId((current) => (current === deletedId ? null : current))
      setSelectedScript(null)
      setFeedback("Script deactivated.")
    } catch (requestError) {
      setError(
        requestError instanceof Error
          ? requestError.message
          : "Could not deactivate script",
      )
    } finally {
      setSaving(false)
    }
  }

  const queueTestCall = async () => {
    if (!selectedScript || !latestCallPrepSnapshot) {
      setError(
        "Select a script and prospecting contact before queueing a call.",
      )
      return
    }

    setTestCallLoading(true)
    setError(null)
    setFeedback(null)
    try {
      const response = await signalloopRequest<TestCallResponse>(
        "/api/v1/calls/test-call",
        {
          method: "POST",
          body: {
            contact_id: latestCallPrepSnapshot.contact_id,
            campaign_id: selectedScript.campaign_id,
            voice_script_id: selectedScript.id,
          },
        },
      )
      await loadIndex()
      setFeedback(`${response.message}.`)
    } catch (requestError) {
      setError(
        requestError instanceof Error
          ? requestError.message
          : "Could not queue test call",
      )
    } finally {
      setTestCallLoading(false)
    }
  }

  return (
    <div className="flex flex-col gap-6">
      <div className="flex items-start justify-between gap-4">
        <div>
          <h1 className="text-3xl font-semibold tracking-tight flex items-center gap-2">
            <Mic2 className="h-7 w-7 text-primary" />
            Voice Agents
          </h1>
          <p className="mt-1 text-sm text-muted-foreground">
            Choose an AI voice profile, manage real campaign scripts, and check
            provider readiness for AI calling.
          </p>
        </div>
        <div className="flex gap-2">
          <Button
            variant="outline"
            onClick={() => void loadIndex()}
            disabled={loading}
          >
            {loading ? (
              <Loader2 className="mr-2 h-4 w-4 animate-spin" />
            ) : (
              <RefreshCw className="mr-2 h-4 w-4" />
            )}
            Refresh
          </Button>
          <Button onClick={openCreateDialog} disabled={campaigns.length === 0}>
            <Plus className="mr-2 h-4 w-4" />
            New script
          </Button>
        </div>
      </div>

      {error && <Alert variant="destructive">{error}</Alert>}
      {feedback && <Alert>{feedback}</Alert>}

      <div className="flex flex-col gap-3 rounded-lg border bg-muted/20 p-4 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <p className="text-sm font-medium">Voice language</p>
          <p className="text-sm text-muted-foreground">
            Used for browser preview and new script starter text.
          </p>
        </div>
        <Select
          value={selectedVoiceLanguageId}
          onValueChange={(value) => {
            const langId = value as VoiceLanguageId
            setSelectedVoiceLanguageId(langId)
            // If the current profile doesn't support the new language, switch to Priya
            const current = VOICE_PROFILES.find(
              (p) => p.id === selectedVoiceProfileId,
            )
            if (current?.languages && !current.languages.includes(langId)) {
              setSelectedVoiceProfileId("priya")
            }
          }}
        >
          <SelectTrigger aria-label="Voice language" className="w-full sm:w-52">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            {VOICE_LANGUAGES.map((language) => (
              <SelectItem key={language.id} value={language.id}>
                {language.label}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>

      <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
        {VOICE_PROFILES.filter(
          (profile) =>
            !profile.languages ||
            profile.languages.includes(selectedVoiceLanguageId),
        ).map((profile) => (
          <VoiceProfileCard
            key={profile.id}
            profile={profile}
            selected={selectedVoiceProfileId === profile.id}
            speaking={speakingProfileId === profile.id}
            voicesReady={voicesReady}
            onSelect={() => handleSelectVoiceProfile(profile.id)}
            onPreview={() => previewVoiceProfile(profile)}
          />
        ))}
      </div>

      {setupOverview && (
        <VoiceReadinessNotice missingItems={missingVoiceReadinessItems} />
      )}

      <VoiceExecutionCard
        callbacksReady={setupOverview?.callbacks.public_host ?? false}
        disabledReason={testCallDisabledReason}
        providerConfigured={voiceIntegration?.configured ?? false}
        providerName={selectedVoiceProviderName}
        selectedScriptName={selectedScript?.name ?? null}
        testContactSummary={
          latestCallPrepSnapshot ? "Latest prospecting contact" : null
        }
        testCallLoading={testCallLoading}
        onQueueTestCall={() => void queueTestCall()}
      />

      <div className="grid gap-6 xl:grid-cols-2">
        <ProspectingCallPrepCard snapshot={latestCallPrepSnapshot} />
        <CallOutcomeIntelligenceCard
          call={latestCallDetail}
          fallbackCall={recentCalls[0] ?? null}
        />
      </div>

      <div className="grid gap-6 xl:grid-cols-[minmax(0,380px)_minmax(0,1fr)]">
        <Card className="border-border/70">
          <CardHeader>
            <div className="space-y-3">
              <div>
                <CardTitle>Campaign voice scripts</CardTitle>
                <CardDescription>
                  Select a campaign to inspect the real scripts already
                  associated with it.
                </CardDescription>
              </div>
              <div className="space-y-2">
                <Label>Campaign</Label>
                <Select
                  value={selectedCampaignId}
                  onValueChange={setSelectedCampaignId}
                >
                  <SelectTrigger>
                    <SelectValue placeholder="Select campaign" />
                  </SelectTrigger>
                  <SelectContent>
                    {campaigns.map((campaign) => (
                      <SelectItem key={campaign.id} value={campaign.id}>
                        {campaign.name}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
            </div>
          </CardHeader>
          <CardContent className="space-y-3">
            {loading && (
              <div className="flex items-center gap-2 text-sm text-muted-foreground">
                <Loader2 className="h-4 w-4 animate-spin" />
                Loading voice scripts...
              </div>
            )}

            {!loading && filteredScripts.length === 0 && (
              <div className="rounded-md border border-dashed p-4 text-sm text-muted-foreground">
                No scripts found for this campaign. Create one to make the voice
                path operational.
              </div>
            )}

            {filteredScripts.map((script) => (
              <button
                key={script.id}
                type="button"
                onClick={() => setSelectedScriptId(script.id)}
                className={`w-full rounded-lg border p-4 text-left transition-colors ${
                  selectedScriptId === script.id
                    ? "border-primary bg-primary/5"
                    : "border-border/70 hover:border-primary/40"
                }`}
              >
                <div className="flex items-start justify-between gap-3">
                  <div>
                    <p className="font-medium">{script.name}</p>
                    <p className="mt-1 text-xs text-muted-foreground">
                      Created {formatDate(script.created_at)}
                    </p>
                  </div>
                  <Badge variant={script.active ? "default" : "outline"}>
                    {script.active ? "Active" : "Inactive"}
                  </Badge>
                </div>
              </button>
            ))}
          </CardContent>
        </Card>

        <Card className="border-border/70">
          <CardHeader>
            <div className="flex flex-wrap items-start justify-between gap-3">
              <div>
                <CardTitle>
                  {selectedScript?.name ?? "Script details"}
                </CardTitle>
                <CardDescription>
                  {selectedScript
                    ? `Campaign: ${campaigns.find((campaign) => campaign.id === selectedScript.campaign_id)?.name ?? "Unknown campaign"}`
                    : "Select a script to see the real parsed preview and campaign association."}
                </CardDescription>
              </div>
              {selectedScript && (
                <div className="flex gap-2">
                  <Button size="sm" variant="outline" onClick={openEditDialog}>
                    <Pencil className="mr-2 h-4 w-4" />
                    Edit
                  </Button>
                  <Button
                    size="sm"
                    variant="ghost"
                    className="text-rose-500 hover:text-rose-600"
                    onClick={deleteSelectedScript}
                    disabled={saving}
                  >
                    <Trash2 className="mr-2 h-4 w-4" />
                    Deactivate
                  </Button>
                </div>
              )}
            </div>
          </CardHeader>
          <CardContent className="space-y-6">
            {!selectedScript && !loading && (
              <div className="rounded-md border border-dashed p-6 text-sm text-muted-foreground">
                Choose a script to view the backend-parsed preview and voice
                readiness context.
              </div>
            )}

            {selectedScript && (
              <>
                <div className="grid gap-4 md:grid-cols-3">
                  <MetricCard
                    label="Status"
                    value={selectedScript.active ? "Active" : "Inactive"}
                  />
                  <MetricCard
                    label="Campaign"
                    value={
                      campaigns.find(
                        (campaign) =>
                          campaign.id === selectedScript.campaign_id,
                      )?.name ?? "Unknown"
                    }
                  />
                  <MetricCard
                    label="Created"
                    value={formatDate(selectedScript.created_at)}
                  />
                </div>

                <div className="space-y-3">
                  <div>
                    <h3 className="font-medium">Script source</h3>
                    <p className="text-sm text-muted-foreground">
                      This is the exact backend-backed script content associated
                      with the selected campaign.
                    </p>
                  </div>
                  <div className="rounded-lg border bg-muted/20 p-4">
                    <pre className="whitespace-pre-wrap text-sm text-foreground">
                      {selectedScript.content}
                    </pre>
                  </div>
                </div>

                <div className="space-y-3">
                  <div>
                    <h3 className="font-medium">Parsed preview</h3>
                    <p className="text-sm text-muted-foreground">
                      Derived from the same backend parser used by the script
                      preview endpoint.
                    </p>
                  </div>

                  <PreviewSection
                    title="Opening pitch"
                    content={
                      selectedScript.parsed?.opening_pitch || "Not provided"
                    }
                  />
                  <PreviewSection
                    title="Fallback"
                    content={
                      selectedScript.parsed?.fallback_response || "Not provided"
                    }
                  />
                  <PreviewSection
                    title="Scheduling question"
                    content={
                      selectedScript.parsed?.scheduling_question ||
                      "Not provided"
                    }
                  />

                  <div className="rounded-lg border p-4">
                    <p className="font-medium">Q&A pairs</p>
                    <div className="mt-3 space-y-3">
                      {selectedScript.parsed?.qa_pairs?.length ? (
                        selectedScript.parsed.qa_pairs.map((pair, index) => (
                          <div
                            key={`${pair.question}-${index}`}
                            className="rounded-md bg-muted/30 p-3"
                          >
                            <p className="text-sm font-medium">
                              Q: {pair.question}
                            </p>
                            <p className="mt-1 text-sm text-muted-foreground">
                              A: {pair.answer}
                            </p>
                          </div>
                        ))
                      ) : (
                        <p className="text-sm text-muted-foreground">
                          No structured Q&A pairs were parsed from this script.
                        </p>
                      )}
                    </div>
                  </div>
                </div>

                {setupOverview && !setupOverview.callbacks.public_host && (
                  <Alert variant="destructive">
                    Voice scripts are saved, but Twilio callbacks still point at
                    a local host. Update the public callback host in workspace
                    setup before treating voice execution as release-ready.
                  </Alert>
                )}
              </>
            )}
          </CardContent>
        </Card>
      </div>

      <Dialog open={dialogOpen} onOpenChange={setDialogOpen}>
        <DialogContent className="max-h-[85vh] overflow-y-auto sm:max-w-3xl">
          <DialogHeader>
            <DialogTitle>
              {editorMode === "create" ? "Create script" : "Edit script"}
            </DialogTitle>
            <DialogDescription>
              Save real campaign voice scripts through the backend script CRUD
              endpoints.
            </DialogDescription>
          </DialogHeader>

          <div className="space-y-6 py-2">
            <div className="grid gap-4 md:grid-cols-2">
              <div className="space-y-2">
                <Label htmlFor="script-name">Script name</Label>
                <Input
                  id="script-name"
                  value={scriptName}
                  onChange={(event) => setScriptName(event.target.value)}
                  placeholder="e.g. Discovery call opener"
                />
              </div>
              <div className="space-y-2">
                <Label>Campaign</Label>
                <Select
                  value={editorCampaignId}
                  onValueChange={setEditorCampaignId}
                >
                  <SelectTrigger>
                    <SelectValue placeholder="Select campaign" />
                  </SelectTrigger>
                  <SelectContent>
                    {campaigns.map((campaign) => (
                      <SelectItem key={campaign.id} value={campaign.id}>
                        {campaign.name}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
            </div>

            {editorMode === "edit" && (
              <div className="space-y-2">
                <Label>Status</Label>
                <Select
                  value={active ? "active" : "inactive"}
                  onValueChange={(value) => setActive(value === "active")}
                >
                  <SelectTrigger>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="active">Active</SelectItem>
                    <SelectItem value="inactive">Inactive</SelectItem>
                  </SelectContent>
                </Select>
              </div>
            )}

            <div className="space-y-2">
              <Label htmlFor="script-content">Script content</Label>
              <Textarea
                id="script-content"
                rows={18}
                value={scriptContent}
                onChange={(event) => setScriptContent(event.target.value)}
                placeholder="Paste the script in the backend markdown format"
                className="font-mono"
              />
            </div>

            <div className="rounded-md border bg-muted/20 p-4 text-sm text-muted-foreground">
              Use the backend script format with sections like{" "}
              <strong>Opening Pitch</strong>, <strong>Q&A</strong>,{" "}
              <strong>Fallback</strong>, and <strong>Scheduling</strong>. If the
              backend rejects the payload, the page keeps the unsaved draft open
              and surfaces the error instead of pretending it saved.
            </div>
          </div>

          <DialogFooter>
            <Button
              variant="outline"
              onClick={() => setDialogOpen(false)}
              disabled={saving}
            >
              Cancel
            </Button>
            <Button
              onClick={() => void saveScript()}
              disabled={
                saving ||
                !scriptName.trim() ||
                !editorCampaignId ||
                !scriptContent.trim()
              }
            >
              {saving ? (
                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
              ) : null}
              {editorMode === "create" ? "Create script" : "Save changes"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  )
}

function VoiceProfileCard({
  profile,
  selected,
  speaking,
  voicesReady,
  onSelect,
  onPreview,
}: {
  profile: VoiceProfile
  selected: boolean
  speaking: boolean
  voicesReady: boolean
  onSelect: () => void
  onPreview: () => void
}) {
  return (
    <Card
      className={selected ? "border-primary bg-primary/5" : "border-border/70"}
    >
      <CardHeader>
        <div className="flex items-start justify-between gap-3">
          <div className="flex min-w-0 gap-3">
            <div
              className={`flex h-10 w-10 items-center justify-center rounded-full text-primary ${speaking ? "bg-primary/25" : "bg-primary/10"}`}
            >
              <User className="h-5 w-5" />
            </div>
            <div className="min-w-0">
              <CardTitle className="text-base">{profile.name}</CardTitle>
              <CardDescription>{profile.accent}</CardDescription>
            </div>
          </div>
          {selected && <Badge>Selected</Badge>}
        </div>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="flex flex-wrap gap-2">
          <Badge variant="secondary">{profile.gender}</Badge>
          <Badge variant="outline">{profile.tone}</Badge>
        </div>
        <p className="text-sm text-muted-foreground">{profile.description}</p>
        <div className="flex flex-wrap gap-2">
          <Button
            type="button"
            variant={selected ? "default" : "outline"}
            size="sm"
            onClick={onSelect}
            aria-label={`Select ${profile.name} voice profile`}
          >
            Use {profile.name}
          </Button>
          <Button
            type="button"
            variant="outline"
            size="sm"
            onClick={onPreview}
            aria-label={
              speaking
                ? `Stop ${profile.name} voice preview`
                : `Preview ${profile.name} voice`
            }
          >
            {speaking ? (
              <Square className="mr-2 h-4 w-4" />
            ) : (
              <Play className="mr-2 h-4 w-4" />
            )}
            {speaking ? "Stop" : "Preview"}
          </Button>
        </div>
        {!voicesReady && (
          <p className="text-xs text-muted-foreground">
            Browser voice preview is loading.
          </p>
        )}
      </CardContent>
    </Card>
  )
}

function ProspectingCallPrepCard({
  snapshot,
}: {
  snapshot: ProspectingResearchResult | null
}) {
  return (
    <Card className="border-border/70">
      <CardHeader>
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <CardTitle>Prospecting call prep</CardTitle>
            <CardDescription>
              Latest research context for outbound voice follow-up.
            </CardDescription>
          </div>
          {snapshot && (
            <Badge variant="outline">{formatDate(snapshot.created_at)}</Badge>
          )}
        </div>
      </CardHeader>
      <CardContent className="space-y-4">
        {snapshot ? (
          <>
            <div className="grid gap-4 lg:grid-cols-[minmax(0,1fr)_minmax(0,1fr)]">
              <div className="rounded-lg border p-4">
                <p className="text-sm font-medium">Account context</p>
                <p className="mt-2 text-sm leading-6 text-muted-foreground">
                  {snapshot.account_summary}
                </p>
              </div>
              <div className="rounded-lg border p-4">
                <p className="text-sm font-medium">Voice opener</p>
                <p className="mt-2 text-sm leading-6 text-muted-foreground">
                  {snapshot.voice_opener}
                </p>
              </div>
            </div>
            <div className="grid gap-4 lg:grid-cols-[minmax(0,1fr)_minmax(0,1fr)]">
              <div className="rounded-lg border p-4">
                <p className="text-sm font-medium">Likely objection</p>
                <p className="mt-2 text-sm leading-6 text-muted-foreground">
                  {snapshot.objections[0] ?? "No objection captured yet."}
                </p>
              </div>
              <div className="rounded-lg border p-4">
                <p className="text-sm font-medium">Next action</p>
                <p className="mt-2 text-sm leading-6 text-muted-foreground">
                  {snapshot.suggested_next_action}
                </p>
              </div>
            </div>
            <div className="flex flex-wrap gap-2">
              {snapshot.sources.map((source) => (
                <Badge
                  key={`${source.label}-${source.summary}`}
                  variant="secondary"
                >
                  {source.label}
                </Badge>
              ))}
            </div>
          </>
        ) : (
          <div className="rounded-md border border-dashed p-4 text-sm text-muted-foreground">
            Run prospecting research to populate call prep for voice follow-up.
          </div>
        )}
      </CardContent>
    </Card>
  )
}

function VoiceExecutionCard({
  callbacksReady,
  disabledReason,
  providerConfigured,
  providerName,
  selectedScriptName,
  testContactSummary,
  testCallLoading,
  onQueueTestCall,
}: {
  callbacksReady: boolean
  disabledReason: string | null
  providerConfigured: boolean
  providerName: string
  selectedScriptName: string | null
  testContactSummary: string | null
  testCallLoading: boolean
  onQueueTestCall: () => void
}) {
  return (
    <Card className="border-border/70">
      <CardHeader>
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <CardTitle>Voice execution</CardTitle>
            <CardDescription>
              Provider, callback, and manual test-call readiness for the
              selected script.
            </CardDescription>
          </div>
          <Badge variant={providerConfigured ? "default" : "destructive"}>
            {providerConfigured ? "Ready" : "Needs setup"}
          </Badge>
        </div>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="grid gap-4 md:grid-cols-3">
          <MetricCard label="Selected provider" value={providerName} />
          <MetricCard
            label="Callbacks"
            value={callbacksReady ? "Public" : "Local only"}
          />
          <MetricCard
            label="Selected script"
            value={selectedScriptName ?? "No script selected"}
          />
        </div>
        <div className="flex flex-col gap-3 rounded-lg border p-4 sm:flex-row sm:items-center sm:justify-between">
          <div className="min-w-0">
            <p className="text-sm font-medium">Manual test call</p>
            <p className="mt-1 line-clamp-2 text-sm text-muted-foreground">
              {testContactSummary ?? "No prospecting contact selected."}
            </p>
            {disabledReason && (
              <p className="mt-2 text-xs text-muted-foreground">
                {disabledReason}
              </p>
            )}
          </div>
          <Button
            type="button"
            className="w-full shrink-0 sm:w-auto"
            onClick={onQueueTestCall}
            disabled={Boolean(disabledReason) || testCallLoading}
          >
            {testCallLoading ? (
              <Loader2 className="mr-2 h-4 w-4 animate-spin" />
            ) : (
              <PhoneCall className="mr-2 h-4 w-4" />
            )}
            Queue test call
          </Button>
        </div>
      </CardContent>
    </Card>
  )
}

function CallOutcomeIntelligenceCard({
  call,
  fallbackCall,
}: {
  call: CallDetail | null
  fallbackCall: CallListItem | null
}) {
  const intelligence = call?.intelligence ?? null
  const sentimentVariant =
    intelligence?.sentiment === "negative"
      ? "destructive"
      : intelligence?.sentiment === "positive"
        ? "default"
        : "secondary"

  return (
    <Card className="border-border/70">
      <CardHeader>
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <CardTitle className="flex items-center gap-2">
              <Brain className="h-5 w-5 text-primary" />
              Call outcome intelligence
            </CardTitle>
            <CardDescription>
              Summary, objection, and next action from the latest call.
            </CardDescription>
          </div>
          {intelligence && (
            <Badge variant={sentimentVariant}>{intelligence.sentiment}</Badge>
          )}
        </div>
      </CardHeader>
      <CardContent className="space-y-4">
        {intelligence ? (
          <>
            <div className="rounded-lg border p-4">
              <p className="text-sm font-medium">Summary</p>
              <p className="mt-2 text-sm leading-6 text-muted-foreground">
                {intelligence.summary}
              </p>
            </div>
            <div className="grid gap-4 lg:grid-cols-2">
              <OutcomeField
                label="Objection"
                value={intelligence.objection ?? "No objection captured."}
              />
              <OutcomeField
                label="Next action"
                value={intelligence.next_action}
              />
            </div>
            <OutcomeField
              label="Recommended follow-up"
              value={intelligence.recommended_follow_up}
            />
          </>
        ) : (
          <div className="rounded-md border border-dashed p-4 text-sm text-muted-foreground">
            {fallbackCall
              ? `Latest call is ${fallbackCall.status}. Intelligence appears after call processing.`
              : "Completed calls will show outcome intelligence here."}
          </div>
        )}
      </CardContent>
    </Card>
  )
}

function OutcomeField({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-lg border p-4">
      <p className="text-sm font-medium">{label}</p>
      <p className="mt-2 text-sm leading-6 text-muted-foreground">{value}</p>
    </div>
  )
}

function VoiceReadinessNotice({
  missingItems,
}: {
  missingItems: Array<{ label: string; ready: boolean }>
}) {
  if (missingItems.length === 0) {
    return null
  }

  return (
    <Alert variant="destructive" className="items-center">
      <TriangleAlert className="mt-0.5 h-4 w-4" />
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <p className="font-medium">Voice readiness needs setup</p>
          <p className="text-sm">
            Configure the missing voice prerequisites in Provider Setup:{" "}
            {missingItems.map((item) => item.label).join(", ")}.
          </p>
        </div>
        <Button asChild variant="outline" size="sm" className="w-fit">
          <Link to="/settings/providers">Configure providers</Link>
        </Button>
      </div>
    </Alert>
  )
}

function MetricCard({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-lg border p-4">
      <p className="text-sm text-muted-foreground">{label}</p>
      <p className="mt-2 text-lg font-semibold break-words">{value}</p>
    </div>
  )
}

function PreviewSection({
  title,
  content,
}: {
  title: string
  content: string
}) {
  return (
    <div className="rounded-lg border p-4">
      <p className="font-medium">{title}</p>
      <p className="mt-2 whitespace-pre-wrap text-sm text-muted-foreground">
        {content}
      </p>
    </div>
  )
}
