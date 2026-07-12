# Architecture & operations reference

Companion to the [README](../README.md): everything needed to run, configure
and extend the project. The README stays the 3-minute overview; this file is
the detail.

## Components

| Layer | What it does |
|---|---|
| `backend/rag/connectors/` | `SourceConnector` interface; `ObsidianConnector` parses frontmatter, inline/nested tags, wikilinks (aliases, `#Heading` forms), strips image embeds, and yields per-note metadata (`note_path`, `note_title`, `folder`, `modified_at`) |
| `backend/rag/ingestion.py` | Heading-aware markdown chunking (`heading_path` metadata, oversized sections sub-split); character chunking for PDF/TXT |
| `backend/rag/sync.py` | Incremental vault sync: content hash per note, chunk ids tracked in `SyncedNote`, unchanged notes skipped without embedding |
| `backend/rag/pipeline.py` | `RAGPipeline`: dense retrieval (Chroma, per-user filter), optional BM25+RRF hybrid, optional cross-encoder rerank with relevance threshold, rewrite policy, streaming and non-streaming query paths |
| `backend/rag/retrieval_config.py` | `RetrievalConfig`: every retrieval flag, env-fed, overridable per eval run |
| `backend/evals/` | Gold set loader/generator, retrieval and answer evaluators, run persistence, markdown report |
| `backend/routes/` | Auth (JWT), chat (`/query`, `/query/stream` SSE, `/history`), documents upload, analytics |
| `frontend/src/` | React SPA: streaming chat (fetch + ReadableStream SSE parsing), source cards with `obsidian://` links, analytics dashboard |

## Retrieval flow

1. **Rewrite policy** (`rewrite_mode`): `auto` rewrites only questions under
   6 words or with anaphoric markers; anaphoric follow-ups with chat history
   are condensed into a standalone question (`CONDENSE_PROMPT`, Haiku).
2. **Candidate retrieval**: dense top-`candidate_k` (Chroma, filtered by
   `user_id`); in hybrid mode also BM25 top-`candidate_k`, fused with
   Reciprocal Rank Fusion (k=60).
3. **Reranking** (optional): candidates scored by `BAAI/bge-reranker-v2-m3`,
   sigmoid-normalized; best `final_k` kept. If every score is below
   `rerank_threshold`, the pipeline answers that nothing relevant was found.
4. **Answering**: `claude-sonnet-4-6` (configurable via `ANSWER_MODEL`),
   structured output on the JSON route, plain-text streaming on the SSE route.

Source metadata exposes `retrieval_mode`, `rrf_score`, `dense_rank`,
`bm25_rank` and `rerank_score` so any ranking can be reconstructed from an
eval run file.

## HTTP API

| Method & path | Description |
|---|---|
| `POST /api/auth/register` | `{email, password}` → `{access_token, user}` |
| `POST /api/auth/login` | `{email, password}` → `{access_token, user}` |
| `GET /api/auth/me` | Authenticated user |
| `POST /api/chat/query` | `{message, session_id?}` → answer, sources, `query_rewritten`, `rewrite_reason`, latency |
| `POST /api/chat/query/stream` | Same input; SSE events `sources` → `delta`* → `done` |
| `GET /api/chat/history` | Sessions with nested messages and persisted sources |
| `POST /api/documents/upload` | Multipart PDF/Markdown/TXT upload |
| `GET /api/documents` | Uploaded documents + chunk counts |
| `GET /api/analytics/summary` | Usage totals, average latency, 7-day trend |

## CLI

```sh
flask --app backend.app obsidian sync --vault <dir> --user <email> [--dry-run]
flask --app backend.app rag generate-goldset --vault <dir> --user <email> --n 60 [--seed 42]
flask --app backend.app rag eval-retrieval --goldset <file> --user <email> [--k 5] [ablation flags]
flask --app backend.app rag eval-answers   --goldset <file> --user <email> [--limit N] [ablation flags]
flask --app backend.app rag eval-report [--type retrieval|answers|all] [--last N]
```

Ablation flags (accepted by both eval commands, overriding the environment
for that run only): `--hybrid/--no-hybrid`, `--rerank/--no-rerank`,
`--rewrite-mode always|auto|never`, `--candidate-k`, `--final-k`,
`--rerank-threshold`.

## Configuration

Copy `.env.example` to `.env`. Key variables:

| Variable | Purpose | Default |
|---|---|---|
| `JWT_SECRET_KEY` | Token signing secret — **required in production** (the app refuses to start without it when `FLASK_ENV=production`) | dev-only fallback |
| `ANTHROPIC_API_KEY` | LLM calls (rewriter, answerer, eval judge/generator) | — |
| `ANSWER_MODEL` | Answering model | `claude-sonnet-4-6` |
| `EMBEDDING_MODEL_NAME` | Dense embedding model | `sentence-transformers/all-MiniLM-L6-v2` |
| `RERANKER_MODEL_NAME` | Cross-encoder model | `BAAI/bge-reranker-v2-m3` |
| `RETRIEVAL_HYBRID` / `RETRIEVAL_RERANK` | Feature flags | `false` / `false` |
| `REWRITE_MODE` | `always` / `auto` / `never` | `auto` |
| `RETRIEVAL_CANDIDATE_K` / `RETRIEVAL_FINAL_K` | Candidate pool / returned chunks | `20` / `5` |
| `RERANK_THRESHOLD` | Relevance gate (sigmoid scale) | `0.3` |
| `CHAT_HISTORY_WINDOW` | Messages passed as condensation context | `6` |
| `DATABASE_URL` | SQLAlchemy URL | `sqlite:///instance/app.db` |
| `RATE_LIMIT` | Per-IP throttle | `60/minute` |
| `FRONTEND_ORIGINS` | CORS allowlist | `http://localhost:5173` |

Frontend: `VITE_API_BASE_URL` (backend URL) and `VITE_OBSIDIAN_VAULT` (vault
name for `obsidian://` citation links) in `frontend/.env.local` — see
`frontend/.env.example`.

## Local development (without Docker)

```sh
uv sync                                  # Python 3.12 env from uv.lock
uv run flask --app backend.app run      # API on :5000
cd frontend && npm install && npm run dev   # SPA on :5173
```

Tests and lint (also run in CI):

```sh
uv run pytest -q
uv run ruff check . && uv run ruff format --check .
```

The test suite runs fully offline: embeddings are deterministic fakes and
every LLM client is replaced by a fixture — no API key needed.

## Data model

`User` → `ChatSession` → `ChatMessage` (sources persisted as JSON),
`UploadedDocument` (dedup by content hash), `SyncedNote` (per-user vault sync
state: `note_path`, `content_hash`, `chunk_ids`), `UsageLog` (latency per
endpoint, feeds the dashboard).
