from backend.rag.pipeline import RAGPipeline


def _make_pipeline(tmp_path):
    return RAGPipeline(persist_directory=str(tmp_path / "vs"), top_k=4)


def test_query_on_empty_knowledge_base(tmp_path):
    pipeline = _make_pipeline(tmp_path)
    result = pipeline.query("anything", user_id=1)
    assert "empty" in result["answer"].lower()
    assert result["sources"] == []


def test_query_answers_with_sources(tmp_path):
    pipeline = _make_pipeline(tmp_path)
    pipeline.ingest_uploaded_text(
        "PostgreSQL uses MVCC for concurrency control.",
        metadata={"source": "db.md", "user_id": 1},
    )

    result = pipeline.query("How does PostgreSQL handle concurrency?", user_id=1)

    # FakeAnswerer/FakeGrader/FakeRewriter from conftest are in play:
    # no network call, deterministic output.
    assert result["answer"].startswith("Answer based on")
    assert result["query_rewritten"] == "How does PostgreSQL handle concurrency?"
    assert len(result["sources"]) >= 1
    assert result["sources"][0]["source"] == "db.md"
    assert all(0.0 <= src["confidence"] <= 1.0 for src in result["sources"])


def test_query_returns_fallback_when_grader_rejects(tmp_path):
    pipeline = _make_pipeline(tmp_path)
    pipeline.ingest_uploaded_text(
        "Totally unrelated content.",
        metadata={"source": "junk.md", "user_id": 1},
    )
    pipeline.grader.grade = lambda question, context_text: "no"

    result = pipeline.query("What is the meaning of life?", user_id=1)

    assert "not appear relevant" in result["answer"]


def test_query_with_no_results_for_user(tmp_path):
    pipeline = _make_pipeline(tmp_path)
    pipeline.ingest_uploaded_text(
        "Content that belongs to someone else.",
        metadata={"source": "other.md", "user_id": 99},
    )

    result = pipeline.query("anything at all", user_id=1)

    assert result["sources"] == []
    assert "No relevant documents" in result["answer"]
