import pytest

from backend.rag.pipeline import RAGPipeline
from backend.rag.retrieval_config import RetrievalConfig
from backend.rag.rewriter import rewrite_reason


class RecordingRewriter:
    def __init__(self):
        self.rewrites = []
        self.condenses = []

    def rewrite(self, question):
        self.rewrites.append(question)
        return f"rewritten: {question}"

    def condense(self, question, history):
        self.condenses.append((question, len(history)))
        return f"condensed: {question}"


@pytest.mark.parametrize(
    ("question", "expected"),
    [
        ("Docker ?", "short"),
        ("Config du reranker ?", "short"),
        ("Comment est-ce qu'il gère la persistance des données au redémarrage ?", "anaphoric"),
        ("Et pour la partie frontend comment est-ce configuré exactement ?", "anaphoric"),
        ("What about the incremental synchronization of larger vaults?", "anaphoric"),
        ("Quel framework backend utilise le projet documenté dans mes notes ?", None),
    ],
)
def test_rewrite_reason(question, expected):
    assert rewrite_reason(question) == expected


def _pipeline(tmp_path, mode):
    config = RetrievalConfig(rewrite_mode=mode)
    pipeline = RAGPipeline(persist_directory=str(tmp_path / "vs"), config=config)
    pipeline._rewriter = RecordingRewriter()
    pipeline.ingest_uploaded_text(
        "Le projet documente un backend Flask avec un vectorstore Chroma.",
        metadata={"source": "projet.md", "user_id": 1},
    )
    return pipeline


def test_auto_mode_rewrites_short_questions(tmp_path):
    pipeline = _pipeline(tmp_path, "auto")
    result = pipeline.query("Backend ?", user_id=1)
    assert result["rewrite_reason"] == "short"
    assert result["query_rewritten"] == "rewritten: Backend ?"
    assert pipeline._rewriter.condenses == []


def test_auto_mode_condenses_anaphoric_questions_with_history(tmp_path):
    pipeline = _pipeline(tmp_path, "auto")
    history = [
        {"role": "user", "content": "Parle-moi du backend Flask."},
        {"role": "assistant", "content": "Le backend utilise Flask et Chroma."},
    ]
    question = "Et pour la persistance des données comment est-ce géré ?"
    result = pipeline.query(question, user_id=1, history=history)
    assert result["rewrite_reason"] == "anaphoric"
    assert result["query_rewritten"] == f"condensed: {question}"
    assert pipeline._rewriter.condenses == [(question, 2)]
    assert pipeline._rewriter.rewrites == []


def test_auto_mode_leaves_normal_questions_untouched(tmp_path):
    pipeline = _pipeline(tmp_path, "auto")
    question = "Quel framework backend utilise le projet documenté dans mes notes ?"
    result = pipeline.query(question, user_id=1)
    assert result["rewrite_reason"] == "none"
    assert result["query_rewritten"] == question
    assert pipeline._rewriter.rewrites == []
    assert pipeline._rewriter.condenses == []


def test_never_mode_never_rewrites(tmp_path):
    pipeline = _pipeline(tmp_path, "never")
    result = pipeline.query("Backend ?", user_id=1)
    assert result["rewrite_reason"] == "none"
    assert result["query_rewritten"] == "Backend ?"
    assert pipeline._rewriter.rewrites == []


def test_always_mode_rewrites_normal_questions(tmp_path):
    pipeline = _pipeline(tmp_path, "always")
    question = "Quel framework backend utilise le projet documenté dans mes notes ?"
    result = pipeline.query(question, user_id=1)
    assert result["rewrite_reason"] == "always"
    assert result["query_rewritten"] == f"rewritten: {question}"
