import json
import subprocess
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path

from ..rag.answerer import DEFAULT_MODEL as ANSWER_MODEL
from ..rag.ingestion import CHUNK_OVERLAP, CHUNK_SIZE, MAX_SECTION_CHARS, SECTION_CHUNK_OVERLAP
from ..rag.pipeline import EMBEDDING_MODEL_NAME, RAGPipeline
from ..rag.reranker import RERANKER_MODEL_NAME
from ..rag.rewriter import DEFAULT_MODEL as REWRITER_MODEL

DEFAULT_RUNS_DIR = "evals/runs"


def _git_short_sha() -> str:
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "--short", "HEAD"], text=True, stderr=subprocess.DEVNULL
        ).strip()
    except (OSError, subprocess.CalledProcessError):
        return "nogit"


def build_config(pipeline: RAGPipeline, **extra) -> dict:
    """Snapshot of everything that can influence the numbers of a run."""
    return {
        "embedding_model": EMBEDDING_MODEL_NAME,
        "retrieval": asdict(pipeline.config),
        "answer_model": ANSWER_MODEL,
        "rewriter_model": REWRITER_MODEL,
        "reranker_model": RERANKER_MODEL_NAME,
        "chunking": {
            "text_chunk_size": CHUNK_SIZE,
            "text_chunk_overlap": CHUNK_OVERLAP,
            "markdown_max_section_chars": MAX_SECTION_CHARS,
            "markdown_section_overlap": SECTION_CHUNK_OVERLAP,
        },
        **extra,
    }


def write_run(
    run_type: str, config: dict, result: dict, runs_dir: str | Path = DEFAULT_RUNS_DIR
) -> Path:
    """Persist a run as evals/runs/{timestamp}_{git-short-sha}.json."""
    now = datetime.now(UTC)
    sha = _git_short_sha()
    directory = Path(runs_dir)
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / f"{now.strftime('%Y%m%d-%H%M%S')}_{sha}.json"

    payload = {
        "run_type": run_type,
        "timestamp": now.isoformat(timespec="seconds"),
        "git_sha": sha,
        "config": config,
        **result,
    }
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def load_runs(runs_dir: str | Path = DEFAULT_RUNS_DIR) -> list[dict]:
    """All runs in chronological order; each dict gains a 'label' key."""
    runs = []
    for path in sorted(Path(runs_dir).glob("*.json")):
        data = json.loads(path.read_text(encoding="utf-8"))
        data["label"] = path.stem
        runs.append(data)
    return runs


def markdown_report(runs: list[dict]) -> str:
    """Comparison table: one column per run, one row per metric."""
    if not runs:
        return "No eval runs found."

    def _flatten(run: dict) -> dict:
        flat = dict(run.get("metrics", {}))
        for tag, tag_metrics in (run.get("by_tag") or {}).items():
            for name, value in tag_metrics.items():
                flat[f"{name} [{tag}]"] = value
        return flat

    flattened = [_flatten(run) for run in runs]
    row_names: list[str] = []
    for flat in flattened:
        for name in flat:
            if name not in row_names:
                row_names.append(name)

    def _fmt(value) -> str:
        if value is None:
            return "—"
        if isinstance(value, float):
            return f"{value:.3f}"
        return str(value)

    header = ["metric"] + [f"{run['label']}<br>({run['run_type']})" for run in runs]
    lines = [
        "| " + " | ".join(header) + " |",
        "|" + "---|" * len(header),
    ]
    for name in row_names:
        cells = [_fmt(flat.get(name)) for flat in flattened]
        lines.append("| " + " | ".join([name] + cells) + " |")
    return "\n".join(lines)
