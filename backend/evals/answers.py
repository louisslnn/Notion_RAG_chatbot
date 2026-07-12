import time

from langchain.chat_models import init_chat_model
from pydantic import BaseModel, Field

from ..rag.pipeline import RAGPipeline
from .goldset import GoldItem
from .metrics import mean

JUDGE_MODEL = "claude-sonnet-4-6"

# USD per million tokens (input, output) - used for cost estimates only.
PRICING_PER_MTOK = {
    "claude-haiku-4-5": (1.0, 5.0),
    "claude-sonnet-4-6": (3.0, 15.0),
}

try:
    from langchain_core.callbacks import get_usage_metadata_callback
except ImportError:  # pragma: no cover - older langchain-core
    get_usage_metadata_callback = None


class AnswerVerdict(BaseModel):
    points_covered: list[bool] = Field(
        description="For each expected point, in order, whether the answer contains it"
    )
    faithfulness: float = Field(
        ge=0.0,
        le=1.0,
        description=(
            "1.0 when every claim in the answer is supported by the retrieved sources, "
            "0.0 when it is unsupported or contradicts them"
        ),
    )


class RefusalVerdict(BaseModel):
    refused: bool = Field(
        description="True if the assistant correctly said it does not know instead of inventing"
    )


ANSWER_JUDGE_PROMPT = """\
You are grading the answer of a RAG assistant over personal notes.

Question:
{question}

Expected factual points a correct answer must contain:
{points}

Assistant's answer:
{answer}

Retrieved source excerpts:
{sources}

1. For each expected point, in order, say whether the answer contains it.
2. Rate faithfulness between 0 and 1: 1.0 when every claim in the answer is
supported by the source excerpts, 0.0 when the answer is unsupported or
contradicts them."""

REFUSAL_JUDGE_PROMPT = """\
A RAG assistant was asked a question whose answer is NOT in the user's notes.
The correct behaviour is to say it does not know or cannot find the answer.

Question:
{question}

Assistant's answer:
{answer}

Did the assistant correctly decline to answer, rather than inventing one?"""


class AnswerJudge:
    """LLM judge with structured output. Injected in tests, real in the CLI."""

    def __init__(self, llm=None):
        self._llm = llm

    @property
    def llm(self):
        if self._llm is None:
            self._llm = init_chat_model(JUDGE_MODEL, model_provider="anthropic", temperature=0.0)
        return self._llm

    def judge_answer(
        self, question: str, expected_points: list[str], answer: str, sources_text: str
    ) -> dict:
        prompt = ANSWER_JUDGE_PROMPT.format(
            question=question,
            points="\n".join(f"{i + 1}. {p}" for i, p in enumerate(expected_points)),
            answer=answer,
            sources=sources_text or "(no sources returned)",
        )
        verdict = self.llm.with_structured_output(AnswerVerdict).invoke(
            [{"role": "user", "content": prompt}]
        )
        covered = list(verdict.points_covered)[: len(expected_points)]
        covered += [False] * (len(expected_points) - len(covered))
        coverage = mean([1.0 if c else 0.0 for c in covered]) if expected_points else 0.0
        return {
            "coverage": round(coverage, 4),
            "faithfulness": round(min(1.0, max(0.0, verdict.faithfulness)), 4),
            "points_covered": covered,
        }

    def judge_refusal(self, question: str, answer: str) -> bool:
        prompt = REFUSAL_JUDGE_PROMPT.format(question=question, answer=answer)
        verdict = self.llm.with_structured_output(RefusalVerdict).invoke(
            [{"role": "user", "content": prompt}]
        )
        return verdict.refused


def _usage_to_dict(usage_metadata: dict) -> dict:
    return {
        model: {
            "input_tokens": data.get("input_tokens", 0),
            "output_tokens": data.get("output_tokens", 0),
        }
        for model, data in usage_metadata.items()
    }


def _estimate_cost(usage: dict | None) -> float | None:
    if not usage:
        return None
    total = 0.0
    priced = False
    for model, data in usage.items():
        for name, (price_in, price_out) in PRICING_PER_MTOK.items():
            if name in model:
                total += data["input_tokens"] / 1e6 * price_in
                total += data["output_tokens"] / 1e6 * price_out
                priced = True
    return round(total, 6) if priced else None


def _tracked(callable_, *args, **kwargs) -> tuple[object, dict | None]:
    """Run callable_ and capture LLM token usage when langchain supports it."""
    if get_usage_metadata_callback is None:
        return callable_(*args, **kwargs), None
    with get_usage_metadata_callback() as cb:
        result = callable_(*args, **kwargs)
    return result, _usage_to_dict(cb.usage_metadata)


def evaluate_answers(
    items: list[GoldItem],
    *,
    pipeline: RAGPipeline,
    user_id: int,
    judge: AnswerJudge | None = None,
    limit: int | None = None,
) -> dict:
    """End-to-end evaluation: query() + LLM judge on every gold question."""
    judge = judge or AnswerJudge()
    per_question = []

    for item in items[:limit]:
        started = time.perf_counter()
        result, query_usage = _tracked(pipeline.query, item.question, user_id=user_id)
        latency_ms = (time.perf_counter() - started) * 1000

        answer = result.get("answer", "")
        sources = result.get("sources") or []
        sources_text = "\n\n".join(
            f"[{src.get('note_path') or src.get('source')}] {src.get('snippet', '')}"
            for src in sources
        )

        entry = {
            "id": item.id,
            "question": item.question,
            "tags": item.tags,
            "expected_note_paths": item.expected_note_paths,
            "retrieved_note_paths": [
                str(src.get("note_path") or src.get("source") or "") for src in sources
            ],
            "answer": answer,
            "latency_ms": round(latency_ms, 1),
            "query_usage": query_usage,
            "query_cost_usd": _estimate_cost(query_usage),
        }

        if item.is_negative:
            refused, judge_usage = _tracked(judge.judge_refusal, item.question, answer)
            entry["refused_correctly"] = bool(refused)
        else:
            verdict, judge_usage = _tracked(
                judge.judge_answer, item.question, item.expected_answer_points, answer, sources_text
            )
            entry.update(verdict)
        entry["judge_cost_usd"] = _estimate_cost(judge_usage)

        per_question.append(entry)

    positives = [q for q in per_question if "refused_correctly" not in q]
    negatives = [q for q in per_question if "refused_correctly" in q]

    metrics = {
        "coverage": round(mean([q["coverage"] for q in positives]), 4),
        "faithfulness": round(mean([q["faithfulness"] for q in positives]), 4),
        "refusal_accuracy": round(
            mean([1.0 if q["refused_correctly"] else 0.0 for q in negatives]), 4
        )
        if negatives
        else None,
        "avg_latency_ms": round(mean([q["latency_ms"] for q in per_question]), 1),
        "total_query_cost_usd": _sum_costs(q["query_cost_usd"] for q in per_question),
        "total_judge_cost_usd": _sum_costs(q["judge_cost_usd"] for q in per_question),
    }
    return {
        "questions_evaluated": len(per_question),
        "metrics": metrics,
        "questions": per_question,
    }


def _sum_costs(costs) -> float | None:
    known = [c for c in costs if c is not None]
    return round(sum(known), 6) if known else None
