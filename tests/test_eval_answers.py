from backend.evals.answers import evaluate_answers
from backend.evals.goldset import GoldItem
from backend.rag.pipeline import RAGPipeline


class FakeJudge:
    def __init__(self):
        self.answer_calls = []
        self.refusal_calls = []

    def judge_answer(self, question, expected_points, answer, sources_text):
        self.answer_calls.append(question)
        covered = [True] + [False] * (len(expected_points) - 1)
        return {
            "coverage": sum(covered) / len(expected_points),
            "faithfulness": 1.0,
            "points_covered": covered,
        }

    def judge_refusal(self, question, answer):
        self.refusal_calls.append(question)
        return True


def _pipeline_with_content(tmp_path):
    pipeline = RAGPipeline(persist_directory=str(tmp_path / "vs"))
    pipeline.ingest_uploaded_text(
        "# Projet\n\nLe backend utilise Flask et Chroma.",
        metadata={"source": "projet.md", "note_path": "projet.md", "user_id": 1},
        content_type="text/markdown",
    )
    return pipeline


def _items():
    return [
        GoldItem(
            id="q001",
            question="Quel framework backend ?",
            expected_note_paths=["projet.md"],
            expected_answer_points=["Flask", "Chroma"],
            tags=["factual"],
        ),
        GoldItem(id="q002", question="Question sans réponse ?", tags=["negative"]),
    ]


def test_evaluate_answers_with_mocked_judge(tmp_path):
    pipeline = _pipeline_with_content(tmp_path)
    judge = FakeJudge()

    result = evaluate_answers(_items(), pipeline=pipeline, user_id=1, judge=judge)

    assert result["questions_evaluated"] == 2
    metrics = result["metrics"]
    assert metrics["coverage"] == 0.5  # 1 of 2 expected points covered
    assert metrics["faithfulness"] == 1.0
    assert metrics["refusal_accuracy"] == 1.0
    assert metrics["avg_latency_ms"] > 0

    detail = {q["id"]: q for q in result["questions"]}
    # FakeAnswerer from conftest produced the answer; judge saw it.
    assert detail["q001"]["answer"].startswith("Answer based on")
    assert detail["q001"]["points_covered"] == [True, False]
    assert detail["q002"]["refused_correctly"] is True
    assert judge.answer_calls == ["Quel framework backend ?"]
    assert judge.refusal_calls == ["Question sans réponse ?"]


def test_evaluate_answers_respects_limit(tmp_path):
    pipeline = _pipeline_with_content(tmp_path)
    result = evaluate_answers(_items(), pipeline=pipeline, user_id=1, judge=FakeJudge(), limit=1)
    assert result["questions_evaluated"] == 1
    assert result["metrics"]["refusal_accuracy"] is None  # no negative evaluated
