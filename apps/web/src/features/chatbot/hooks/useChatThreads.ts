import { useCallback, useEffect, useMemo, useState } from "react"
import { toast } from "sonner"

import {
  type ChatbotThreadDetail,
  type ChatbotThreadFilters,
  type ChatbotThreadSummary,
  getChatbotThread,
  listChatbotThreads,
  reopenChatbotThread,
  replyToChatbotThread,
  resolveChatbotThread,
  streamChatbotInboxEvents,
} from "@/features/chatbot/api"

export function useChatThreads(initialThreadId?: string | null) {
  const [filters, setFilters] = useState<ChatbotThreadFilters>({ status: "all", channel_type: "all" })
  const [threads, setThreads] = useState<ChatbotThreadSummary[]>([])
  const [selectedThreadId, setSelectedThreadId] = useState<string | null>(initialThreadId || null)
  const [detail, setDetail] = useState<ChatbotThreadDetail | null>(null)
  const [loading, setLoading] = useState(true)
  const [detailLoading, setDetailLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [sseConnected, setSseConnected] = useState(false)

  const loadThreads = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const response = await listChatbotThreads(filters)
      setThreads(response.data)
      setSelectedThreadId((current) => current || initialThreadId || response.data[0]?.id || null)
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : "Failed to load inbox")
    } finally {
      setLoading(false)
    }
  }, [filters, initialThreadId])

  useEffect(() => {
    if (initialThreadId) {
      setSelectedThreadId(initialThreadId)
    }
  }, [initialThreadId])

  const loadDetail = useCallback(async (threadId: string | null) => {
    if (!threadId) {
      setDetail(null)
      return
    }
    setDetailLoading(true)
    try {
      setDetail(await getChatbotThread(threadId))
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : "Failed to load thread")
    } finally {
      setDetailLoading(false)
    }
  }, [])

  useEffect(() => {
    void loadThreads()
  }, [loadThreads])

  useEffect(() => {
    void loadDetail(selectedThreadId)
  }, [loadDetail, selectedThreadId])

  useEffect(() => {
    const controller = new AbortController()
    let cancelled = false
    let fallback: number | undefined

    const startFallback = () => {
      setSseConnected(false)
      if (!fallback) fallback = window.setInterval(() => void loadThreads(), 30000)
    }

    const stopFallback = () => {
      if (fallback) {
        window.clearInterval(fallback)
        fallback = undefined
      }
    }

    void streamChatbotInboxEvents({
      signal: controller.signal,
      onOpen: () => {
        setSseConnected(true)
        stopFallback()
      },
      onInbox: () => {
        toast.info("New messaging inbox activity")
        void loadThreads()
      },
    }).then(() => {
      if (!cancelled) startFallback()
    }).catch(() => {
      if (!cancelled && !controller.signal.aborted) startFallback()
    })

    return () => {
      cancelled = true
      controller.abort()
      stopFallback()
    }
  }, [loadThreads])

  const selectedThread = useMemo(
    () => threads.find((thread) => thread.id === selectedThreadId) || null,
    [threads, selectedThreadId],
  )

  const sendReply = async (message: string) => {
    if (!selectedThreadId) return
    const response = await replyToChatbotThread(selectedThreadId, message)
    setDetail(response.thread)
    await loadThreads()
  }

  const resolveSelected = async () => {
    if (!selectedThreadId) return
    const response = await resolveChatbotThread(selectedThreadId)
    setDetail(response.thread)
    await loadThreads()
  }

  const reopenSelected = async () => {
    if (!selectedThreadId) return
    const response = await reopenChatbotThread(selectedThreadId)
    setDetail(response.thread)
    await loadThreads()
  }

  return {
    detail,
    detailLoading,
    error,
    filters,
    loading,
    refresh: loadThreads,
    reopenSelected,
    resolveSelected,
    selectedThread,
    selectedThreadId,
    sendReply,
    setFilters,
    setSelectedThreadId,
    sseConnected,
    threads,
  }
}
