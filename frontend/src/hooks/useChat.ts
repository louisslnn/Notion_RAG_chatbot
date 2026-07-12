import { useCallback, useEffect, useMemo, useState } from "react";
import client, { API_BASE_URL } from "../api/client";

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

export type StreamingExchange = {
  userContent: string;
  answer: string;
  sources: Source[];
};

type SseEvent = { event: string; data: any };

function parseSseFrames(buffer: string): { events: SseEvent[]; rest: string } {
  const frames = buffer.split("\n\n");
  const rest = frames.pop() ?? "";
  const events: SseEvent[] = [];
  for (const frame of frames) {
    let event = "message";
    let data = "";
    for (const line of frame.split("\n")) {
      if (line.startsWith("event: ")) event = line.slice(7).trim();
      else if (line.startsWith("data: ")) data += line.slice(6);
    }
    if (data) {
      try {
        events.push({ event, data: JSON.parse(data) });
      } catch {
        // ignore malformed frames
      }
    }
  }
  return { events, rest };
}

export function useChat() {
  const [sessions, setSessions] = useState<Session[]>([]);
  const [activeSessionId, setActiveSessionId] = useState<number | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [streaming, setStreaming] = useState<StreamingExchange | null>(null);

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
      setStreaming({ userContent: content, answer: "", sources: [] });

      let answer = "";
      let sources: Source[] = [];
      let sessionId: number | null = null;
      let latencyMs: number | null = null;

      try {
        const token = localStorage.getItem("token");
        const response = await fetch(`${API_BASE_URL}/api/chat/query/stream`, {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            ...(token ? { Authorization: `Bearer ${token}` } : {}),
          },
          body: JSON.stringify({ message: content, session_id: activeSessionId }),
        });
        if (!response.ok || !response.body) {
          throw new Error(`Stream failed (${response.status})`);
        }

        const reader = response.body.getReader();
        const decoder = new TextDecoder();
        let buffer = "";

        for (;;) {
          const { done, value } = await reader.read();
          if (done) break;
          buffer += decoder.decode(value, { stream: true });
          const { events, rest } = parseSseFrames(buffer);
          buffer = rest;
          for (const { event, data } of events) {
            if (event === "sources") {
              sources = data.sources ?? [];
              setStreaming((prev) => (prev ? { ...prev, sources } : prev));
            } else if (event === "delta") {
              answer += data.text ?? "";
              setStreaming((prev) => (prev ? { ...prev, answer } : prev));
            } else if (event === "done") {
              sessionId = data.session_id;
              latencyMs = data.latency_ms ?? null;
            }
          }
        }
        if (sessionId === null) {
          throw new Error("Stream ended without a done event");
        }

        const newUserMessage: ChatMessage = {
          role: "user",
          content,
          createdAt: new Date().toISOString(),
        };
        const newAssistantMessage: ChatMessage = {
          role: "assistant",
          content: answer,
          sources,
          createdAt: new Date().toISOString(),
          latencyMs,
        };

        setSessions((prev) => {
          const sessionIndex = prev.findIndex((session) => session.sessionId === sessionId);
          if (sessionIndex === -1) {
            return [
              {
                sessionId: sessionId as number,
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
        setActiveSessionId((prev) => prev ?? sessionId);
      } catch (err: any) {
        setError(err?.message || "Failed to send message.");
      } finally {
        setStreaming(null);
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
    streaming,
    sendMessage,
    createSession,
    reloadHistory: loadHistory,
  };
}

