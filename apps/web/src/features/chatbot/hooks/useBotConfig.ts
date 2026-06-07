import { useEffect, useState } from "react"

import {
  type ChatbotConfig,
  type ChatbotConfigUpdate,
  getChatbotConfig,
  updateChatbotConfig,
} from "@/features/chatbot/api"

export function useBotConfig() {
  const [config, setConfig] = useState<ChatbotConfig | null>(null)
  const [draft, setDraft] = useState<ChatbotConfig | null>(null)
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const load = async () => {
    setLoading(true)
    setError(null)
    try {
      const response = await getChatbotConfig()
      setConfig(response)
      setDraft(response)
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : "Failed to load settings")
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    void load()
  }, [])

  const dirty = JSON.stringify(config) !== JSON.stringify(draft)

  const discard = () => setDraft(config)

  const save = async () => {
    if (!draft) return
    setSaving(true)
    setError(null)
    try {
      const payload: ChatbotConfigUpdate = {
        ai_disclosure: draft.ai_disclosure,
        bot_name: draft.bot_name,
        business_hours: draft.business_hours,
        escalation_message: draft.escalation_message,
        greeting_message: draft.greeting_message,
        lead_capture: draft.lead_capture,
        out_of_hours_message: draft.out_of_hours_message,
        persona: draft.persona,
        reindex_schedule_time: draft.reindex_schedule_time,
        retention_days: draft.retention_days,
        token_cap_per_session: draft.token_cap_per_session,
      }
      const response = await updateChatbotConfig(payload)
      setConfig(response)
      setDraft(response)
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : "Failed to save settings")
      throw requestError
    } finally {
      setSaving(false)
    }
  }

  return { config, dirty, discard, draft, error, loading, refresh: load, save, saving, setDraft }
}

