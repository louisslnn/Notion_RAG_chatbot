# RAG evaluation harness

This directory holds the gold set and the evaluation run history used to
measure retrieval and answer quality — and to prove, with numbers, the impact
of every pipeline change (hybrid search, reranking, chunking tweaks, ...).

## Gold set format (`goldset.jsonl`)

One JSON object per line:

```json
{"id": "q001", "question": "Quel framework backend utilise le Projet X ?", "expected_note_paths": ["Projets/Projet X.md"], "expected_answer_points": ["le backend utilise Flask"], "tags": ["factual"]}
```

| Field | Meaning |
|---|---|
| `id` | Unique identifier (`q001`, `q002`, ...) |
| `question` | The question, as a user would ask it |
| `expected_note_paths` | Vault-relative paths of the note(s) containing the answer |
| `expected_answer_points` | Short factual points a correct answer must contain |
| `tags` | One of `factual`, `multi-note`, `negative` |

Tags:

- **factual** — the answer lives in a single note.
- **multi-note** — a complete answer needs several notes (`expected_note_paths`
  lists all of them).
- **negative** — the answer is NOT in the vault; the system must say it does
  not know. `expected_note_paths` and `expected_answer_points` are empty.

## Workflow: draft → human validation → gold set

1. Generate a draft with the assisted generator:

   ```sh
   flask --app backend.app rag generate-goldset \
       --vault ~/MonVault --user you@example.com --n 60 --out evals/goldset.draft.jsonl
   ```

2. **Review every line by hand.** The draft is LLM-generated and is NOT ground
   truth: fix wrong `expected_answer_points`, remove ambiguous questions,
   check that negatives are really absent from the vault, adjust
   `expected_note_paths` if a fact also lives elsewhere.

3. Rename the validated file to `evals/goldset.jsonl` and commit it.

Draft files (`*.draft.jsonl`) are git-ignored on purpose; only the reviewed
gold set belongs in the repo.

## Running evaluations

```sh
# Retrieval only — no LLM call, no API key needed
flask --app backend.app rag eval-retrieval --goldset evals/goldset.jsonl --user you@example.com

# End-to-end (answers judged by an LLM) — needs ANTHROPIC_API_KEY
flask --app backend.app rag eval-answers --goldset evals/goldset.jsonl --user you@example.com

# Compare past runs (markdown table, ready for the README)
flask --app backend.app rag eval-report
```

Each run writes `evals/runs/{timestamp}_{git-sha}.json` containing the
pipeline configuration, the aggregated metrics (global and per tag) and the
per-question detail (expected vs retrieved notes, generated answer, judge
verdict) so every failure can be inspected.

## Metrics

Retrieval (computed on the unique note paths of the retrieved chunks, in
rank order, against `expected_note_paths`; negatives are skipped):

- **recall@k** (k = 1, 3, 5) — fraction of expected notes present in the top k.
- **MRR** — 1 / rank of the first expected note (0 if absent).
- **nDCG@5** — rank-discounted gain, rewards putting expected notes first.

End-to-end (LLM judge, structured output):

- **coverage** — fraction of `expected_answer_points` present in the answer.
- **faithfulness** — is the answer fully supported by the retrieved sources?
- **refusal accuracy** — for negatives: did the system correctly decline?
- Plus latency per question and estimated LLM cost when token usage is
  available.
