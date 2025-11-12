import { useEffect, useState } from "react";
import { motion } from "framer-motion";
import client from "../api/client";

type Summary = {
  usage: {
    total_calls: number;
    average_latency_ms: number;
  };
  totals: {
    sessions: number;
    assistant_messages: number;
    documents: number;
  };
  last_7_days: Record<string, number>;
};

const cardVariants = {
  hidden: { opacity: 0, y: 12 },
  visible: { opacity: 1, y: 0 },
};

function Dashboard() {
  const [summary, setSummary] = useState<Summary | null>(null);
  const [recentSessions, setRecentSessions] = useState<
    { sessionId: number; title: string; createdAt: string; messages: number }[]
  >([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const fetchSummary = async () => {
      try {
        const { data } = await client.get("/api/analytics/summary");
        setSummary(data);
      } catch (err) {
        setError("Unable to load analytics.");
      } finally {
        setLoading(false);
      }
    };
    const fetchHistory = async () => {
      try {
        const { data } = await client.get("/api/chat/history");
        const mapped = data.sessions.slice(0, 5).map((session: any) => ({
          sessionId: session.session_id,
          title: session.title,
          createdAt: session.created_at,
          messages: session.messages.length,
        }));
        setRecentSessions(mapped);
      } catch (err) {
        // ignore; analytics already has error handling
      }
    };
    fetchSummary();
    fetchHistory();
  }, []);

  if (loading) {
    return (
      <div className="flex flex-1 items-center justify-center bg-surface">
        <div className="animate-pulse rounded-lg bg-panel px-6 py-4 shadow-md">Loading analytics...</div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex flex-1 items-center justify-center bg-surface">
        <div className="rounded bg-error/10 px-6 py-4 text-error">{error}</div>
      </div>
    );
  }

  return (
    <div className="flex flex-1 flex-col gap-6 overflow-y-auto bg-surface p-6">
      <div className="grid gap-4 md:grid-cols-3">
        <motion.div
          variants={cardVariants}
          initial="hidden"
          animate="visible"
          transition={{ delay: 0.05 }}
          className="rounded-xl border border-border bg-panel p-5 shadow"
        >
          <p className="text-sm text-muted">Total Queries</p>
          <p className="mt-2 text-3xl font-semibold text-foreground">{summary?.usage.total_calls ?? 0}</p>
        </motion.div>

        <motion.div
          variants={cardVariants}
          initial="hidden"
          animate="visible"
          transition={{ delay: 0.15 }}
          className="rounded-xl border border-border bg-panel p-5 shadow"
        >
          <p className="text-sm text-muted">Average Latency</p>
          <p className="mt-2 text-3xl font-semibold text-foreground">
            {(summary?.usage.average_latency_ms ?? 0).toFixed(0)} ms
          </p>
        </motion.div>

        <motion.div
          variants={cardVariants}
          initial="hidden"
          animate="visible"
          transition={{ delay: 0.25 }}
          className="rounded-xl border border-border bg-panel p-5 shadow"
        >
          <p className="text-sm text-muted">Documents Ingested</p>
          <p className="mt-2 text-3xl font-semibold text-foreground">{summary?.totals.documents ?? 0}</p>
        </motion.div>
      </div>

      <section className="grid gap-6 md:grid-cols-2">
        <motion.div
          variants={cardVariants}
          initial="hidden"
          animate="visible"
          transition={{ delay: 0.35 }}
          className="rounded-xl border border-border bg-panel p-6 shadow"
        >
          <h3 className="text-sm font-semibold uppercase tracking-wide text-muted">Recent Sessions</h3>
          <ul className="mt-4 space-y-3 text-sm">
            {recentSessions.map((session) => (
              <li key={session.sessionId} className="rounded-lg border border-transparent bg-hover/40 p-3">
                <p className="font-semibold text-foreground">{session.title || "Untitled session"}</p>
                <p className="text-xs text-muted">
                  {new Date(session.createdAt).toLocaleString([], {
                    hour: "2-digit",
                    minute: "2-digit",
                    month: "short",
                    day: "numeric",
                  })}
                </p>
                <p className="mt-2 text-xs text-muted">
                  Messages: <span className="font-semibold text-foreground">{session.messages}</span>
                </p>
              </li>
            ))}
          </ul>
        </motion.div>

        <motion.div
          variants={cardVariants}
          initial="hidden"
          animate="visible"
          transition={{ delay: 0.45 }}
          className="rounded-xl border border-border bg-panel p-6 shadow"
        >
          <h3 className="text-sm font-semibold uppercase tracking-wide text-muted">Usage (7 days)</h3>
          <ul className="mt-4 space-y-2 text-sm">
            {Object.entries(summary?.last_7_days || {}).map(([day, count]) => (
              <li key={day} className="flex items-center justify-between rounded border border-border/40 px-3 py-2">
                <span className="text-muted">{day}</span>
                <span className="font-semibold text-foreground">{count}</span>
              </li>
            ))}
            {Object.keys(summary?.last_7_days || {}).length === 0 && (
              <li className="rounded border border-dashed border-border px-3 py-5 text-center text-muted">
                Run some queries to populate the usage timeline.
              </li>
            )}
          </ul>
        </motion.div>
      </section>
    </div>
  );
}

export default Dashboard;

