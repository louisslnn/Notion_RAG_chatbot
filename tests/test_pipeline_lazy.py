from backend.rag import pipeline as pipeline_module
from backend.rag.pipeline import RAGPipeline


class ExplodingClient:
    """Fails loudly if any LLM client is instantiated."""

    def __init__(self, *args, **kwargs):
        raise AssertionError("LLM client instantiated during a retrieval-only path")


def test_retrieve_never_instantiates_llm_clients(tmp_path, monkeypatch):
    monkeypatch.setattr(pipeline_module, "AnswerGenerator", ExplodingClient)
    monkeypatch.setattr(pipeline_module, "ContextGrader", ExplodingClient)
    monkeypatch.setattr(pipeline_module, "QueryRewriter", ExplodingClient)
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)

    pipeline = RAGPipeline(persist_directory=str(tmp_path / "vs"))
    pipeline.ingest_uploaded_text(
        "# Note\n\nDu contenu à retrouver.",
        metadata={"source": "note.md", "user_id": 1},
        content_type="text/markdown",
    )

    hits = pipeline.retrieve("contenu", user_id=1, top_k=3)

    assert hits
    assert hits[0]["metadata"]["user_id"] == 1
    assert set(hits[0]) == {"content", "score", "metadata"}


def test_query_still_uses_llm_components(tmp_path, monkeypatch):
    # Sanity check: query() does reach the (fake) LLM components.
    pipeline = RAGPipeline(persist_directory=str(tmp_path / "vs"))
    pipeline.ingest_uploaded_text(
        "# Note\n\nDu contenu.", metadata={"source": "note.md", "user_id": 1}
    )
    result = pipeline.query("question", user_id=1)
    assert result["answer"].startswith("Answer based on")
