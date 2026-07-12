from ..rag.pipeline import RAGPipeline
from .goldset import GoldItem
from .metrics import mean, mrr, ndcg_at_k, recall_at_k, unique_ordered

RECALL_KS = (1, 3, 5)


def _retrieved_note_paths(hits: list[dict]) -> list[str]:
    return unique_ordered(
        [
            str(hit["metadata"].get("note_path") or hit["metadata"].get("source") or "")
            for hit in hits
        ]
    )


def evaluate_retrieval(
    items: list[GoldItem], *, pipeline: RAGPipeline, user_id: int, k: int = 5
) -> dict:
    """Retrieval-only evaluation: no rewriter, no grader, no answerer.

    Negative questions are skipped (they have no expected notes). Metrics are
    computed on the unique note paths of the retrieved chunks, in rank order.
    """
    per_question = []
    for item in items:
        if item.is_negative:
            continue

        hits = pipeline.retrieve(item.question, user_id=user_id, top_k=k)
        retrieved = _retrieved_note_paths(hits)

        question_metrics = {
            f"recall@{kk}": recall_at_k(item.expected_note_paths, retrieved, kk)
            for kk in RECALL_KS
            if kk <= k
        }
        question_metrics["mrr"] = mrr(item.expected_note_paths, retrieved)
        question_metrics["ndcg@5"] = ndcg_at_k(item.expected_note_paths, retrieved, 5)

        per_question.append(
            {
                "id": item.id,
                "question": item.question,
                "tags": item.tags,
                "expected_note_paths": item.expected_note_paths,
                "retrieved_note_paths": retrieved,
                "metrics": question_metrics,
            }
        )

    if not per_question:
        raise ValueError("The gold set contains no non-negative question")

    metric_names = list(per_question[0]["metrics"])

    def _aggregate(questions):
        return {
            name: round(mean([q["metrics"][name] for q in questions]), 4) for name in metric_names
        }

    tags = sorted({tag for q in per_question for tag in q["tags"]})
    return {
        "k": k,
        "questions_evaluated": len(per_question),
        "metrics": _aggregate(per_question),
        "by_tag": {tag: _aggregate([q for q in per_question if tag in q["tags"]]) for tag in tags},
        "questions": per_question,
    }
