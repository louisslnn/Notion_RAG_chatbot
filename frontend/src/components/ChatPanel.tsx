import { FormEvent, useEffect, useRef, useState } from "react";
import { AnimatePresence, motion } from "framer-motion";
import MessageBubble from "./MessageBubble";
import { useChat } from "../hooks/useChat";

function ChatPanel() {
  const {
    sessions,
    activeSession,
    activeSessionId,
    setActiveSessionId,
    loading,
    error,
    sendMessage,
    createSession,
  } = useChat();
  const [message, setMessage] = useState("");
  const messageEndRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    if (messageEndRef.current) {
      messageEndRef.current.scrollIntoView({ behavior: "smooth" });
    }
  }, [activeSession?.messages]);

  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!message.trim()) return;
    await sendMessage(message.trim());
    setMessage("");
  };

  return (
    <div className="flex h-full flex-1 flex-col md:flex-row">
      <aside className="border-b border-r border-border bg-panel/70 p-4 md:w-64 md:border-b-0">
        <div className="flex items-center justify-between">
          <h2 className="text-sm font-semibold uppercase tracking-wide text-muted">Sessions</h2>
          <button
            type="button"
            onClick={createSession}
            className="rounded bg-accent/90 px-3 py-1 text-xs font-semibold text-white shadow hover:bg-accent"
          >
            New
          </button>
        </div>
        <div className="mt-4 flex flex-col gap-2 overflow-y-auto">
          {sessions.map((session) => (
            <button
              key={session.sessionId}
              type="button"
              onClick={() => setActiveSessionId(session.sessionId)}
              className={[
                "rounded-lg border px-3 py-2 text-left text-sm transition",
                session.sessionId === activeSessionId
                  ? "border-accent bg-accent/10 text-foreground shadow-lg shadow-accent/20"
                  : "border-transparent bg-hover/40 text-muted hover:border-border hover:text-foreground",
              ].join(" ")}
            >
              <p className="font-semibold">{session.title || "Untitled session"}</p>
              <p className="text-xs text-muted">
                {new Date(session.createdAt).toLocaleString([], { hour: "2-digit", minute: "2-digit" })}
              </p>
            </button>
          ))}
        </div>
      </aside>

      <section className="flex flex-1 flex-col">
        <div className="flex-1 space-y-6 overflow-y-auto bg-surface p-6">
          <AnimatePresence>
            {activeSession?.messages.map((msg, index) => (
              <MessageBubble
                key={`${msg.role}-${index}-${msg.createdAt}`}
                role={msg.role}
                content={msg.content}
                createdAt={msg.createdAt}
                sources={msg.sources}
                latencyMs={msg.latencyMs ?? null}
              />
            ))}
          </AnimatePresence>
          <div ref={messageEndRef} />
          {error ? <div className="rounded bg-error/10 p-3 text-sm text-error">{error}</div> : null}
          {!activeSession?.messages.length && (
            <div className="flex h-full items-center justify-center text-sm text-muted">
              Start a conversation to see responses and rich source citations.
            </div>
          )}
        </div>

        <form onSubmit={handleSubmit} className="border-t border-border bg-panel/70 p-4 backdrop-blur">
          <div className="flex items-end gap-3">
            <textarea
              value={message}
              onChange={(event) => setMessage(event.target.value)}
              placeholder="Ask about your Notion knowledge base..."
              className="min-h-[3rem] flex-1 resize-none rounded-lg border border-border bg-surface px-3 py-2 text-sm text-foreground shadow focus:border-accent focus:outline-none focus:ring-2 focus:ring-accent/40"
            />
            <button
              type="submit"
              disabled={loading}
              className="rounded-lg bg-gradient-to-r from-accent to-indigo-500 px-5 py-2 text-sm font-semibold text-white shadow-lg transition hover:brightness-105 disabled:cursor-not-allowed disabled:opacity-60"
            >
              {loading ? "Thinking..." : "Send"}
            </button>
          </div>
        </form>
      </section>
    </div>
  );
}

export default ChatPanel;

