import { motion } from "framer-motion";

type Source = {
  source: string;
  confidence: number;
  score: number;
  snippet: string;
  note_title?: string;
  heading_path?: string;
  note_path?: string;
  metadata?: Record<string, unknown>;
};

const OBSIDIAN_VAULT = import.meta.env.VITE_OBSIDIAN_VAULT as string | undefined;

function sourceLabel(source: Source): string {
  if (source.note_title) {
    return source.heading_path
      ? `${source.note_title} > ${source.heading_path}`
      : source.note_title;
  }
  return source.source;
}

function obsidianUrl(notePath: string): string {
  return `obsidian://open?vault=${encodeURIComponent(OBSIDIAN_VAULT ?? "")}&file=${encodeURIComponent(notePath)}`;
}

function SourceList({ sources }: { sources: Source[] }) {
  if (!sources?.length) return null;

  return (
    <div className="mt-3 space-y-2">
      <p className="text-xs uppercase tracking-wide text-muted">Sources</p>
      <div className="grid gap-2 md:grid-cols-2">
        {sources.map((source) => (
          <motion.article
            key={`${source.source}-${source.score}`}
            initial={{ opacity: 0, y: 6 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.25 }}
            className="rounded-lg border border-border bg-panel/80 p-3 text-xs shadow-sm backdrop-blur"
          >
            <div className="flex items-center justify-between gap-2">
              {source.note_path && OBSIDIAN_VAULT ? (
                <a
                  href={obsidianUrl(source.note_path)}
                  className="font-semibold text-foreground underline-offset-2 hover:text-accent hover:underline"
                >
                  {sourceLabel(source)}
                </a>
              ) : (
                <span className="font-semibold text-foreground">{sourceLabel(source)}</span>
              )}
              <span className="rounded bg-accent/10 px-2 py-0.5 font-mono text-[10px] text-accent">
                {(source.confidence * 100).toFixed(0)}%
              </span>
            </div>
            <p className="mt-2 line-clamp-4 text-muted">{source.snippet}</p>
          </motion.article>
        ))}
      </div>
    </div>
  );
}

export default SourceList;
