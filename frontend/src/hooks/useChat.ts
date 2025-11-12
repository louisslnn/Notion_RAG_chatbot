import { useCallback, useEffect, useMemo, useState } from "react";
import client from "../api/client";

export type Source = {
  source: string;
  confidence: number;
  score: number;
  snippet: string;
  metadata?: Record<string, unknown>;
};

export type ChatMessage = {
  id?: number;
  role: "user" | "assistant";
  content: string;
  createdAt?: string;
  sources?: Source[];
  latencyMs?: number | null;
};

type Session = {
  sessionId: number;
  title: string;
  createdAt: string;
  messages: ChatMessage[];
};

export function useChat() {
  const [sessions, setSessions] = useState<Session[]>([]);
  const [activeSessionId, setActiveSessionId] = useState<number | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const loadHistory = useCallback(async () => {
    try {
      const { data } = await client.get("/api/chat/history");
      const mapped: Session[] = data.sessions.map((session: any) => ({
        sessionId: session.session_id,
        title: session.title,
        createdAt: session.created_at,
        messages: session.messages.map((msg: any) => ({
          id: msg.id,
          role: msg.role,
          content: msg.content,
          createdAt: msg.created_at,
          sources: msg.sources,
          latencyMs: msg.response_time_ms,
        })),
      }));
      setSessions(mapped);
      if (mapped.length && !activeSessionId) {
        setActiveSessionId(mapped[0].sessionId);
      }
    } catch (err) {
      setError("Failed to load history.");
    }
  }, [activeSessionId]);

  useEffect(() => {
    loadHistory();
  }, [loadHistory]);

  const activeSession = useMemo(
    () => sessions.find((session) => session.sessionId === activeSessionId),
    [sessions, activeSessionId],
  );

  const sendMessage = useCallback(
    async (content: string) => {
      if (!content.trim()) return;
      setLoading(true);
      setError(null);
      try {
        const { data } = await client.post("/api/chat/query", {
          message: content,
          session_id: activeSessionId,
        });

        const newUserMessage: ChatMessage = {
          role: "user",
          content,
          createdAt: new Date().toISOString(),
        };
        const newAssistantMessage: ChatMessage = {
          role: "assistant",
          content: data.answer,
          sources: data.sources,
          createdAt: new Date().toISOString(),
          latencyMs: data.latency_ms,
        };

        setSessions((prev) => {
          const sessionIndex = prev.findIndex((session) => session.sessionId === data.session_id);
          if (sessionIndex === -1) {
            return [
              {
                sessionId: data.session_id,
                title: content.slice(0, 36) || "New session",
                createdAt: new Date().toISOString(),
                messages: [newUserMessage, newAssistantMessage],
              },
              ...prev,
            ];
          }
          const updated = [...prev];
          updated[sessionIndex] = {
            ...updated[sessionIndex],
            messages: [...updated[sessionIndex].messages, newUserMessage, newAssistantMessage],
          };
          return updated;
        });
        setActiveSessionId((prev) => prev ?? data.session_id);
      } catch (err: any) {
        setError(err?.response?.data?.error || "Failed to send message.");
      } finally {
        setLoading(false);
      }
    },
    [activeSessionId],
  );

  const createSession = useCallback(() => {
    setActiveSessionId(null);
  }, []);

  return {
    sessions,
    activeSession,
    activeSessionId,
    setActiveSessionId,
    loading,
    error,
    sendMessage,
    createSession,
    reloadHistory: loadHistory,
  };
}

