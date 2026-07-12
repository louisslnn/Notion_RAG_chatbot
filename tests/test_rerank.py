from backend.rag.pipeline import RAGPipeline
from backend.rag.retrieval_config import RetrievalConfig


class InjectedReranker:
    """Scores driven by content keywords, recorded for assertions."""

    def __init__(self, scores_by_keyword, default=0.1):
        self.scores_by_keyword = scores_by_keyword
        self.default = default
        self.calls = []

    def score(self, query, texts):
        self.calls.append((query, list(texts)))
        return [
            next(
                (score for kw, score in self.scores_by_keyword.items() if kw in text),
                self.default,
            )
            for text in texts
        ]


def _pipeline(tmp_path, **config_kwargs):
    config = RetrievalConfig(rerank_enabled=True, **config_kwargs)
    return RAGPipeline(persist_directory=str(tmp_path / "vs"), config=config)


def _ingest(pipeline):
    for source, text in [
        ("alpha.md", "Contenu alpha sur la configuration du serveur."),
        ("beta.md", "Contenu beta sur la configuration du serveur."),
        ("gamma.md", "Contenu gamma sur la configuration du serveur."),
    ]:
        pipeline.ingest_uploaded_text(text, metadata={"source": source, "user_id": 1})


def test_reranker_orders_final_hits(tmp_path):
    pipeline = _pipeline(tmp_path, final_k=2)
    reranker = InjectedReranker({"beta": 0.95, "gamma": 0.8, "alpha": 0.4})
    pipeline._reranker = reranker
    _ingest(pipeline)

    hits = pipeline.retrieve("configuration serveur", user_id=1)

    assert [hit["metadata"]["source"] for hit in hits] == ["beta.md", "gamma.md"]
    assert hits[0]["metadata"]["rerank_score"] == 0.95
    assert hits[0]["score"] == 0.95
    # The reranker saw the whole candidate pool, not just final_k.
    assert len(reranker.calls[0][1]) == 3


def test_query_falls_back_when_every_score_is_below_threshold(tmp_path):
    pipeline = _pipeline(tmp_path, final_k=3, rerank_threshold=0.5)
    pipeline._reranker = InjectedReranker({}, default=0.2)
    _ingest(pipeline)

    result = pipeline.query("question sans rapport", user_id=1)

    assert "not appear relevant" in result["answer"]
    assert result["sources"]  # sources still exposed for inspection


def test_query_answers_when_one_score_clears_threshold(tmp_path):
    pipeline = _pipeline(tmp_path, final_k=3, rerank_threshold=0.5)
    pipeline._reranker = InjectedReranker({"beta": 0.9}, default=0.2)
    _ingest(pipeline)

    result = pipeline.query("configuration beta", user_id=1)

    assert result["answer"].startswith("Answer based on")
    assert result["sources"][0]["metadata"]["source"] == "beta.md"


def test_retrieve_does_not_apply_the_threshold(tmp_path):
    # The eval harness needs the ranked list even when scores are low.
    pipeline = _pipeline(tmp_path, final_k=3, rerank_threshold=0.9)
    pipeline._reranker = InjectedReranker({}, default=0.1)
    _ingest(pipeline)

    hits = pipeline.retrieve("n'importe quoi", user_id=1)
    assert len(hits) == 3
    assert all(hit["metadata"]["rerank_score"] == 0.1 for hit in hits)
