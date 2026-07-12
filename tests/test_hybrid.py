from backend.rag.pipeline import RAGPipeline
from backend.rag.retrieval_config import RetrievalConfig

DISTRACTORS = [
    ("a.md", "Notes de réunion hebdomadaire sur la roadmap produit et les priorités."),
    ("b.md", "Recette de cuisine familiale transmise depuis plusieurs générations."),
    ("c.md", "Compte rendu de lecture sur les architectures distribuées modernes."),
    ("d.md", "Idées de cadeaux pour les prochaines fêtes de fin d'année."),
    ("e.md", "Liste de courses et budget mensuel pour la colocation."),
    ("f.md", "Plan d'entraînement course à pied sur douze semaines."),
]
RARE_NOTE = ("z.md", "La clé de chiffrement est stockée dans le composant zorglub du backend.")
QUERY = "où est configuré zorglub ?"


def _ingest_all(pipeline, user_id=1):
    for source, text in [*DISTRACTORS, RARE_NOTE]:
        pipeline.ingest_uploaded_text(text, metadata={"source": source, "user_id": user_id})


def _pipeline(tmp_path, **config_kwargs):
    config = RetrievalConfig(**config_kwargs)
    return RAGPipeline(persist_directory=str(tmp_path / "vs"), config=config)


def test_bm25_lifts_chunk_missed_by_dense_retrieval(tmp_path):
    pipeline = _pipeline(tmp_path, hybrid_enabled=True, final_k=3)
    _ingest_all(pipeline)

    # Dense-only: the fake embeddings have no lexical notion, the rare-token
    # note is not the top hit (deterministic with DeterministicFakeEmbedding).
    dense_pipeline = _pipeline(tmp_path, hybrid_enabled=False, final_k=3)
    dense_top = dense_pipeline.retrieve(QUERY, user_id=1)[0]["metadata"]["source"]
    assert dense_top != "z.md"

    # Hybrid: BM25 ranks it first on the rare token, RRF pushes it on top.
    hits = pipeline.retrieve(QUERY, user_id=1)
    top = hits[0]
    assert top["metadata"]["source"] == "z.md"
    assert top["metadata"]["retrieval_mode"] == "hybrid"
    assert top["metadata"]["bm25_rank"] == 1
    assert top["metadata"]["rrf_score"] > 0
    assert top["score"] == max(hit["score"] for hit in hits)


def test_hybrid_hits_keep_public_shape(tmp_path):
    pipeline = _pipeline(tmp_path, hybrid_enabled=True, final_k=2)
    _ingest_all(pipeline)
    hits = pipeline.retrieve(QUERY, user_id=1)
    assert len(hits) == 2
    assert all(set(hit) == {"content", "score", "metadata"} for hit in hits)


def test_bm25_index_is_isolated_per_user(tmp_path):
    pipeline = _pipeline(tmp_path, hybrid_enabled=True, final_k=5)
    _ingest_all(pipeline, user_id=1)
    pipeline.ingest_uploaded_text(
        "Notes personnelles d'un autre utilisateur sans rapport.",
        metadata={"source": "other.md", "user_id": 2},
    )

    hits_user2 = pipeline.retrieve(QUERY, user_id=2)
    assert all(hit["metadata"]["user_id"] == 2 for hit in hits_user2)
    assert all(hit["metadata"]["source"] != "z.md" for hit in hits_user2)

    # And user 1 still sees only their own chunks.
    hits_user1 = pipeline.retrieve(QUERY, user_id=1)
    assert all(hit["metadata"]["user_id"] == 1 for hit in hits_user1)


def test_bm25_index_invalidated_after_deletion(tmp_path):
    pipeline = _pipeline(tmp_path, hybrid_enabled=True, final_k=5)
    _ingest_all(pipeline)

    ids = pipeline._load_vectorstore().get(where={"user_id": 1})["ids"]
    # Warm the BM25 cache, then delete everything for the user.
    assert pipeline.retrieve(QUERY, user_id=1)
    pipeline.delete_chunks(ids, user_id=1)

    assert pipeline.retrieve(QUERY, user_id=1) == []
