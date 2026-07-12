import os
from collections.abc import Iterable
from dataclasses import replace
from pathlib import Path
from threading import RLock

from langchain_chroma import Chroma
from langchain_core.documents import Document
from langchain_huggingface import HuggingFaceEmbeddings

from .answerer import AnswerGenerator
from .bm25 import UserBM25Index
from .fusion import rrf_fuse
from .ingestion import chunk_content, documents_from_texts, hash_content
from .reranker import Reranker
from .retrieval_config import RetrievalConfig
from .rewriter import QueryRewriter, rewrite_reason

EMBEDDING_MODEL_NAME = os.getenv("EMBEDDING_MODEL_NAME", "sentence-transformers/all-MiniLM-L6-v2")


def _sanitize_metadata(metadata: dict) -> dict:
    """Chroma only accepts scalar metadata values; flatten everything else."""
    clean: dict = {}
    for key, value in metadata.items():
        if value is None or (isinstance(value, (list, tuple)) and not value):
            continue
        if isinstance(value, (str, int, float, bool)):
            clean[key] = value
        elif isinstance(value, (list, tuple)):
            clean[key] = ", ".join(str(item) for item in value)
        else:
            clean[key] = str(value)
    return clean


class RAGPipeline:
    def __init__(
        self,
        persist_directory: str,
        top_k: int | None = None,
        config: RetrievalConfig | None = None,
    ):
        self.persist_directory = Path(persist_directory)
        if config is None:
            config = RetrievalConfig.from_env()
            if top_k is not None:
                config = replace(config, final_k=top_k)
        self.config = config
        self._lock = RLock()
        self._vectorstore: Chroma | None = None
        # Per-user BM25 indexes, rebuilt lazily from Chroma after invalidation.
        self._bm25_cache: dict[int, UserBM25Index] = {}
        self.embedding = HuggingFaceEmbeddings(model_name=EMBEDDING_MODEL_NAME)
        # LLM clients are created lazily so retrieval-only usage (retrieve(),
        # ingestion, evals) works without an Anthropic API key.
        self._answerer: AnswerGenerator | None = None
        self._rewriter: QueryRewriter | None = None
        self._reranker: Reranker | None = None

        self.persist_directory.mkdir(parents=True, exist_ok=True)

    @property
    def answerer(self) -> AnswerGenerator:
        if self._answerer is None:
            self._answerer = AnswerGenerator()
        return self._answerer

    @property
    def reranker(self) -> Reranker:
        if self._reranker is None:
            self._reranker = Reranker()
        return self._reranker

    @property
    def rewriter(self) -> QueryRewriter:
        if self._rewriter is None:
            self._rewriter = QueryRewriter()
        return self._rewriter

    def _load_vectorstore(self) -> Chroma:
        if self._vectorstore is None:
            self._vectorstore = Chroma(
                embedding_function=self.embedding,
                persist_directory=str(self.persist_directory),
            )
        return self._vectorstore

    @staticmethod
    def _collection_count(vectorstore: Chroma) -> int:
        try:
            return vectorstore._collection.count()  # type: ignore[attr-defined]
        except AttributeError:
            return 0

    def ingest_documents(self, docs: list[Document], ids: list[str] | None = None) -> int:
        if not docs:
            return 0
        if ids is not None and len(ids) != len(docs):
            raise ValueError("ids must match docs one-to-one")
        for doc in docs:
            if doc.metadata.get("user_id") is None:
                raise ValueError("Every ingested document must carry a user_id in its metadata")
            doc.metadata = _sanitize_metadata(doc.metadata)
        with self._lock:
            vectorstore = self._load_vectorstore()
            if ids is None:
                vectorstore.add_documents(docs)
            else:
                vectorstore.add_documents(docs, ids=ids)
            for doc in docs:
                self._bm25_cache.pop(doc.metadata["user_id"], None)
        return len(docs)

    def delete_chunks(self, chunk_ids: list[str], user_id: int | None = None) -> None:
        if not chunk_ids:
            return
        with self._lock:
            self._load_vectorstore().delete(ids=list(chunk_ids))
            if user_id is None:
                self._bm25_cache.clear()
            else:
                self._bm25_cache.pop(user_id, None)

    def ingest_texts(self, texts: Iterable[str], base_metadata: dict | None = None) -> int:
        docs = documents_from_texts(texts, base_metadata=base_metadata)
        return self.ingest_documents(docs)

    def ingest_uploaded_text(
        self, content: str, metadata: dict | None = None, content_type: str | None = None
    ) -> dict[str, int]:
        docs = chunk_content(content, metadata=metadata, content_type=content_type)
        added = self.ingest_documents(docs)
        return {"chunks_added": added, "content_hash": hash_content(content)}

    def _dense_hits(self, query: str, user_id: int, k: int) -> list[dict]:
        results = self._load_vectorstore().similarity_search_with_relevance_scores(
            query, k=k, filter={"user_id": user_id}
        )
        return [
            {
                "id": doc.id,
                "content": doc.page_content,
                "score": float(score),
                "metadata": dict(doc.metadata),
            }
            for doc, score in results
        ]

    def _bm25_index(self, user_id: int) -> UserBM25Index:
        index = self._bm25_cache.get(user_id)
        if index is None:
            data = self._load_vectorstore().get(
                where={"user_id": user_id}, include=["documents", "metadatas"]
            )
            index = UserBM25Index(
                ids=data["ids"],
                contents=data["documents"] or [],
                metadatas=data["metadatas"] or [],
            )
            self._bm25_cache[user_id] = index
        return index

    def _hybrid_candidates(self, query: str, user_id: int) -> list[dict]:
        """Dense + BM25 candidates fused with Reciprocal Rank Fusion."""
        candidate_k = self.config.candidate_k
        dense = self._dense_hits(query, user_id, candidate_k)
        bm25_hits = self._bm25_index(user_id).search(query, candidate_k)

        rrf_scores = rrf_fuse([[hit["id"] for hit in dense], [hit.chunk_id for hit in bm25_hits]])

        merged: dict[str, dict] = {}
        for rank, hit in enumerate(dense, start=1):
            merged[hit["id"]] = {
                "content": hit["content"],
                "metadata": hit["metadata"],
                "dense_rank": rank,
            }
        for hit in bm25_hits:
            entry = merged.setdefault(
                hit.chunk_id, {"content": hit.content, "metadata": dict(hit.metadata)}
            )
            entry["bm25_rank"] = hit.rank

        candidates = []
        for chunk_id, entry in merged.items():
            metadata = dict(entry["metadata"])
            metadata["retrieval_mode"] = "hybrid"
            metadata["rrf_score"] = round(rrf_scores[chunk_id], 6)
            for key in ("dense_rank", "bm25_rank"):
                if key in entry:
                    metadata[key] = entry[key]
            candidates.append(
                {"content": entry["content"], "score": rrf_scores[chunk_id], "metadata": metadata}
            )
        candidates.sort(key=lambda candidate: candidate["score"], reverse=True)
        return candidates

    def retrieve(self, query: str, *, user_id: int, top_k: int | None = None) -> list[dict]:
        """User-filtered retrieval: no rewriter, no answerer.

        Returns one dict per chunk: {content, score, metadata}, best first.
        In hybrid mode the score is the RRF score and the metadata carries
        retrieval_mode, rrf_score and the individual dense/bm25 ranks.
        """
        vectorstore = self._load_vectorstore()
        if self._collection_count(vectorstore) == 0:
            return []
        k_final = top_k or self.config.final_k
        # Reranking needs a wide candidate pool even in dense-only mode.
        dense_k = self.config.candidate_k if self.config.rerank_enabled else k_final

        if self.config.hybrid_enabled:
            candidates = self._hybrid_candidates(query, user_id)
        else:
            candidates = [
                {
                    "content": hit["content"],
                    "score": hit["score"],
                    "metadata": {
                        **hit["metadata"],
                        "retrieval_mode": "dense",
                        "dense_rank": rank,
                    },
                }
                for rank, hit in enumerate(self._dense_hits(query, user_id, dense_k), start=1)
            ]

        if self.config.rerank_enabled and candidates:
            candidates = self._rerank(query, candidates[: self.config.candidate_k])
        return candidates[:k_final]

    def _rerank(self, query: str, candidates: list[dict]) -> list[dict]:
        scores = self.reranker.score(query, [candidate["content"] for candidate in candidates])
        for candidate, score in zip(candidates, scores, strict=True):
            candidate["score"] = score
            candidate["metadata"]["rerank_score"] = round(score, 6)
        candidates.sort(key=lambda candidate: candidate["score"], reverse=True)
        return candidates

    def _maybe_rewrite(self, query: str, history: list[dict]) -> tuple[str, str]:
        """Apply the configured rewrite policy; returns (query, reason)."""
        mode = self.config.rewrite_mode
        if mode == "never":
            return query, "none"
        reason = rewrite_reason(query)
        if mode == "auto" and reason is None:
            return query, "none"
        if reason == "anaphoric" and history:
            return self.rewriter.condense(query, history), "anaphoric"
        return self.rewriter.rewrite(query), reason or "always"

    def query(
        self,
        query: str,
        *,
        user_id: int,
        top_k: int | None = None,
        history: list[dict] | None = None,
    ) -> dict:
        vectorstore = self._load_vectorstore()
        if self._collection_count(vectorstore) == 0:
            return {
                "answer": (
                    "Knowledge base is empty. Upload documents or sync Notion to get started."
                ),
                "sources": [],
                "query_original": query,
            }

        rewritten_query, reason = self._maybe_rewrite(query, history or [])
        k = top_k or self.config.final_k
        hits = self.retrieve(rewritten_query, user_id=user_id, top_k=k)

        if not hits:
            return {
                "answer": "No relevant documents were found for the query.",
                "sources": [],
                "query_original": query,
                "query_rewritten": rewritten_query,
                "rewrite_reason": reason,
            }

        chunks = []
        source_entries = []
        for hit in hits[: max(3, k)]:
            content = hit["content"]
            metadata = hit["metadata"]
            score = hit["score"]
            chunks.append(content)
            confidence = min(1.0, max(0.0, score))
            entry = {
                "source": metadata.get("source", "unknown"),
                "score": score,
                "confidence": round(confidence, 3),
                "metadata": metadata,
                "snippet": content[:280] + ("..." if len(content) > 280 else ""),
                # Full chunk text for internal consumers (eval judge); the HTTP
                # routes strip it before persisting or returning sources.
                "content": content,
            }
            for key in ("note_title", "heading_path", "note_path"):
                value = metadata.get(key)
                if value:
                    entry[key] = value
            source_entries.append(entry)

        # The binary LLM grader is replaced by a threshold on the cross-encoder
        # score: if no chunk clears it, the pipeline says it found nothing.
        if self.config.rerank_enabled:
            best_score = max(hit["metadata"].get("rerank_score", 0.0) for hit in hits)
            if best_score < self.config.rerank_threshold:
                return {
                    "answer": (
                        "Retrieved notes do not appear relevant. Refine the query or add documents."
                    ),
                    "sources": source_entries[:3],
                    "query_original": query,
                    "query_rewritten": rewritten_query,
                    "rewrite_reason": reason,
                }

        answer = self.answerer.generate(rewritten_query, chunks)
        return {
            "answer": answer,
            "sources": source_entries[:3],
            "query_original": query,
            "query_rewritten": rewritten_query,
            "rewrite_reason": reason,
        }


_pipeline: RAGPipeline | None = None


def get_pipeline(persist_directory: str, top_k: int = 4) -> RAGPipeline:
    global _pipeline
    if _pipeline is None:
        _pipeline = RAGPipeline(persist_directory=persist_directory, top_k=top_k)
    return _pipeline
