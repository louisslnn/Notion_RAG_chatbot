# Quickstart Guide

This guide walks through essential environment variables, startup commands, document seeding, analytics verification, and optional Notion ingestion.

---

## 1. Environment Variables (`.env`)

Create a `.env` file in the project root with the following entries. Values marked **required** must be set explicitly:

1. `FLASK_APP=backend.app:create_app`
2. `FLASK_ENV=development` (set to `production` when deploying)
3. `JWT_SECRET_KEY=<strong-random-string>` **required**
4. `DATABASE_URL=sqlite:///instance/app.db` (swap for PostgreSQL in prod)
5. `UPLOAD_FOLDER=storage/uploads`
6. `VECTOR_STORE_FOLDER=storage/vectorstore`
7. `RATE_LIMIT=60/minute` (adjust per user/IP throttle policy)
8. `FRONTEND_ORIGINS=http://localhost:5173` (comma-separate additional origins)
9. `EMBEDDING_MODEL_NAME=sentence-transformers/all-MiniLM-L6-v2`

LLM and external service credentials:

- `ANTHROPIC_API_KEY=<your-anthropic-key>` **required for answering/grading**
- `NOTION_TOKEN=<your-notion-integration-token>` (only if syncing Notion)

> TIP: with `python-dotenv` installed, `flask run` and the backend automatically pick up `.env`.

---

## 2. Start the Backend

```bash
python -m venv .venv
source .venv/bin/activate             # Windows: .venv\Scripts\activate
pip install -r requirements.txt

flask run
```

The API serves at `http://localhost:5000`.

---

## 3. Start the Frontend

After the backend is running and `.env` is configured correctly, the SPA can be launched with:

```bash
cd frontend
npm install          # first run only
npm run dev
```

By default Vite listens on `http://localhost:5173`. If you changed the backend host/port, set `VITE_API_BASE_URL` in `frontend/.env` (or export via shell) before `npm run dev`.

---

## 4. Seed Documents & Verify Analytics

### Option A — Web UI
1. Visit `http://localhost:5173/upload`.
2. Authenticate (register/login) if prompted.
3. Drop a PDF, Markdown (`.md`), or plain text file.
4. Confirm the success toast showing chunk count and ingestion latency.

### Option B — API

```bash
curl -X POST http://localhost:5000/api/documents/upload \
  -H "Authorization: Bearer <JWT_FROM_LOGIN>" \
  -F "file=@/absolute/path/to/doc.pdf"
```

### Validate Analytics
1. Send a few chat queries from the UI (or via `POST /api/chat/query`).
2. Open the Dashboard tab or call the endpoint directly:
   ```bash
   curl -H "Authorization: Bearer <JWT>" \
     http://localhost:5000/api/analytics/summary | jq
   ```
3. Confirm the response contains `totals`, `usage.total_calls`, and `last_7_days` entries reflecting your recent actions.

---

## 5. Optional: Notion Ingestion

To re-enable Notion syncing:
1. Set `NOTION_TOKEN` in `.env` to your integration secret.
2. Review `backend/rag/notion.py` for `get_note_texts()` and related helpers.
3. Implement a sync job (Celery task, scheduled script, or CLI command) that:
   - Fetches current Notion page IDs.
   - Calls `page_to_text`/`get_note_texts`.
   - Pipes the resulting strings into `RAGPipeline.ingest_texts(...)`.
4. Run the job before redeploying so the vector store is up-to-date.

---

You’re now ready to search, ingest, and monitor usage in the Notion RAG workspace. Happy building! 🚀

