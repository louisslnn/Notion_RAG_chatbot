# RAG evaluation harness

This directory holds the gold set and the evaluation run history used to
measure retrieval and answer quality — and to prove, with numbers, the impact
of every pipeline change (hybrid search, reranking, chunking tweaks, ...).

## Methodology, end to end

1. **Assisted generation.** `flask rag generate-goldset` samples vault notes
   (weighted by size, seeded for reproducibility) and drafts questions with
   `claude-haiku-4-5`: ~75% single-note factual, ~15% multi-note (built from
   wikilink-connected pairs when available), ~10% negative.
2. **Human validation — mandatory.** The draft is reviewed line by line:
   wrong answer points fixed, ambiguous questions removed, negatives checked
   to be truly absent from the vault, `expected_note_paths` completed when a
   fact also lives elsewhere. Only then is the file renamed `goldset.jsonl`
   and committed. Generated output is never treated as ground truth.
3. **Baseline.** One `eval-retrieval` and one `eval-answers` run with every
   feature flag off, committed to `runs/`. This is the reference row of the
   ablation table.
4. **Ablations.** One flag changes at a time (`--hybrid`, `--rerank`,
   `--rewrite-mode`, ...) on the same gold set and the same synced vault
   state. Each run file records the full pipeline config and the git SHA, so
   any number can be traced to an exact code + flag combination. Run files
   are committed: the README table must be regenerable from them.

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

## Metric definitions (exact)

Retrieval metrics are computed on the **unique note paths** of the retrieved
chunks, in rank order (first occurrence wins), against `expected_note_paths`.
Negative questions are skipped — they have no expected notes.

- **recall@k** (k = 1, 3, 5) — `|expected ∩ top-k| / |expected|`.
- **MRR** — `1 / rank` of the first retrieved note that is expected; 0 if
  none is retrieved.
- **nDCG@5** — binary relevance: `DCG = Σ 1/log2(rank+1)` over expected notes
  in the top 5, normalized by the ideal DCG (all expected notes first).

End-to-end metrics (LLM judge, `claude-sonnet-4-6`, structured output):

- **coverage** — the judge marks each `expected_answer_point` as present or
  absent in the answer; coverage is the fraction marked present.
- **faithfulness** — 0–1: is every claim in the answer supported by the
  retrieved chunks? The judge sees the **full chunk contents**.
- **refusal accuracy** — negatives only: did the system correctly say it
  does not know, rather than inventing an answer?
- Plus latency per question, and token usage / estimated USD cost (query and
  judge tracked separately) when the usage callback is available.

## Methodological caveats

- **The judge is a model grading a model.** Coverage and faithfulness are
  useful as *comparative* signals between runs on the same gold set; they
  are not absolute quality guarantees, and judge biases (leniency,
  self-consistency) apply uniformly but silently. Spot-check per-question
  verdicts in the run files when a delta looks surprising.
- **Faithfulness scope.** Early versions judged faithfulness against the
  280-character public snippets, which over-flagged unsupported claims; this
  was fixed (Phase 2) — the judge now receives the full chunk content while
  the HTTP API keeps returning snippets only.
- **Single-user, single-vault gold set.** Numbers quantify component impact
  on one real corpus. They do not claim general-domain performance, and the
  per-tag breakdown matters: multi-note and negative subsets are small, so
  read them with their question counts in mind.
- **Determinism.** Gold set sampling is seeded; retrieval evals involve no
  LLM. Answer evals depend on non-deterministic LLM output — compare trends,
  not single-question flips.
