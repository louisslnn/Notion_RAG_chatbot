import { FormEvent, useState } from "react";
import { motion } from "framer-motion";
import client from "../api/client";

function UploadPage() {
  const [file, setFile] = useState<File | null>(null);
  const [status, setStatus] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!file) {
      setError("Select a PDF or markdown file first.");
      return;
    }
    setError(null);
    setStatus(null);
    setLoading(true);
    const formData = new FormData();
    formData.append("file", file);

    try {
      const { data } = await client.post("/api/documents/upload", formData, {
        headers: { "Content-Type": "multipart/form-data" },
      });
      setStatus(`Ingested ${data.chunks_ingested} chunks in ${data.latency_ms} ms.`);
    } catch (err: any) {
      setError(err?.response?.data?.error || "Upload failed.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="flex flex-1 flex-col gap-6 overflow-y-auto bg-surface p-6">
      <motion.div
        initial={{ opacity: 0, y: 12 }}
        animate={{ opacity: 1, y: 0 }}
        className="rounded-xl border border-dashed border-accent/40 bg-panel/70 p-8 text-center shadow"
      >
        <h2 className="text-lg font-semibold text-foreground">Bring new context into the workspace</h2>
        <p className="mt-2 text-sm text-muted">
          Drop PDFs or markdown docs. We split, embed, and index them for high signal retrieval.
        </p>
      </motion.div>

      <form
        onSubmit={handleSubmit}
        className="rounded-xl border border-border bg-panel/80 p-6 shadow backdrop-blur md:max-w-2xl"
      >
        <label
          htmlFor="file"
          className="flex cursor-pointer flex-col items-center justify-center gap-2 rounded-lg border-2 border-dashed border-border bg-hover/40 p-10 text-center text-muted transition hover:border-accent hover:bg-hover/80"
        >
          <span className="text-sm font-semibold text-foreground">
            {file ? file.name : "Click to select a document"}
          </span>
          <span className="text-xs text-muted">Supported: PDF, Markdown (.md), Plain text</span>
          <input
            id="file"
            type="file"
            className="hidden"
            onChange={(event) => {
              const next = event.target.files?.[0] ?? null;
              setFile(next);
            }}
            accept=".pdf,.md,.txt"
          />
        </label>

        <button
          type="submit"
          className="mt-6 w-full rounded-lg bg-gradient-to-r from-accent to-indigo-500 px-4 py-2 text-sm font-semibold text-white shadow-lg transition hover:brightness-105 disabled:cursor-not-allowed disabled:opacity-60"
          disabled={loading}
        >
          {loading ? "Uploading..." : "Upload & Ingest"}
        </button>
        {status ? <p className="mt-4 rounded bg-success/10 p-3 text-sm text-success">{status}</p> : null}
        {error ? <p className="mt-4 rounded bg-error/10 p-3 text-sm text-error">{error}</p> : null}
      </form>
    </div>
  );
}

export default UploadPage;

