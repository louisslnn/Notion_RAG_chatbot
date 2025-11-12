import { motion } from "framer-motion";
import SourceList from "./SourceList";

type Source = {
  source: string;
  confidence: number;
  score: number;
  snippet: string;
  metadata?: Record<string, unknown>;
};

type MessageBubbleProps = {
  role: "user" | "assistant";
  content: string;
  createdAt?: string;
  sources?: Source[];
  latencyMs?: number | null;
};

function formatTimestamp(value?: string) {
  if (!value) return "";
  const date = new Date(value);
  return date.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
}

function MessageBubble({ role, content, createdAt, sources, latencyMs }: MessageBubbleProps) {
  const isUser = role === "user";

  return (
    <motion.div
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.25 }}
      className={`flex flex-col ${isUser ? "items-end" : "items-start"}`}
    >
      <div
        className={[
          "max-w-2xl rounded-2xl px-4 py-3 shadow-lg transition",
          isUser
            ? "bg-gradient-to-r from-accent to-indigo-500 text-white"
            : "bg-panel/90 text-foreground backdrop-blur md:max-w-3xl",
        ].join(" ")}
      >
        <p className="prose-sm whitespace-pre-wrap text-sm leading-relaxed">{content}</p>
        {!isUser && (
          <div className="mt-3 flex items-center gap-3 text-[10px] uppercase tracking-wide text-muted">
            {latencyMs ? <span>{latencyMs.toFixed(0)} ms</span> : null}
            {createdAt ? <span>{formatTimestamp(createdAt)}</span> : null}
          </div>
        )}
      </div>
      {!isUser && sources && sources.length > 0 ? <SourceList sources={sources} /> : null}
    </motion.div>
  );
}

export default MessageBubble;

