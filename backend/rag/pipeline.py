import os
from collections.abc import Iterable
from dataclasses import replace
from pathlib import Path
from threading import RLock

from langchain_chroma import Chroma
from langchain_core.documents import Document
from langchain_huggingface import HuggingFaceEmbeddings

from .answerer import AnswerGenerator
from .grader import ContextGrader
from .ingestion import chunk_content, documents_from_texts, hash_content
from .retrieval_config import RetrievalConfig
from .rewriter import QueryRewriter

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
        self.embedding = HuggingFaceEmbeddings(model_name=EMBEDDING_MODEL_NAME)
        # LLM clients are created lazily so retrieval-only usage (retrieve(),
        # ingestion, evals) works without an Anthropic API key.
        self._answerer: AnswerGenerator | None = None
        self._grader: ContextGrader | None = None
        self._rewriter: QueryRewriter | None = None

        self.persist_directory.mkdir(parents=True, exist_ok=True)

    @property
    def answerer(self) -> AnswerGenerator:
        if self._answerer is None:
            self._answerer = AnswerGenerator()
        return self._answerer

    @property
    def grader(self) -> ContextGrader:
        if self._grader is None:
            self._grader = ContextGrader()
        return self._grader

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
        return len(docs)

    def delete_chunks(self, chunk_ids: list[str]) -> None:
        if not chunk_ids:
            return
        with self._lock:
            self._load_vectorstore().delete(ids=list(chunk_ids))

    def ingest_texts(self, texts: Iterable[str], base_metadata: dict | None = None) -> int:
        docs = documents_from_texts(texts, base_metadata=base_metadata)
        return self.ingest_documents(docs)

    def ingest_uploaded_text(
        self, content: str, metadata: dict | None = None, content_type: str | None = None
    ) -> dict[str, int]:
        docs = chunk_content(content, metadata=metadata, content_type=content_type)
        added = self.ingest_documents(docs)
        return {"chunks_added": added, "content_hash": hash_content(content)}

    def retrieve(self, query: str, *, user_id: int, top_k: int | None = None) -> list[dict]:
        """User-filtered vector search only: no rewriter, no grader, no answerer.

        Returns one dict per chunk: {content, score, metadata}, best first.
        """
        vectorstore = self._load_vectorstore()
        if self._collection_count(vectorstore) == 0:
            return []
        k = top_k or self.config.final_k
        results = vectorstore.similarity_search_with_relevance_scores(
            query, k=k, filter={"user_id": user_id}
        )
        return [
            {"content": doc.page_content, "score": float(score), "metadata": doc.metadata}
            for doc, score in results
        ]

    def query(self, query: str, *, user_id: int, top_k: int | None = None) -> dict:
        vectorstore = self._load_vectorstore()
        if self._collection_count(vectorstore) == 0:
            return {
                "answer": (
                    "Knowledge base is empty. Upload documents or sync Notion to get started."
                ),
                "sources": [],
                "query_original": query,
            }

        rewritten_query = self.rewriter.rewrite(query)
        k = top_k or self.config.final_k
        hits = self.retrieve(rewritten_query, user_id=user_id, top_k=k)

        if not hits:
            return {
                "answer": "No relevant documents were found for the query.",
                "sources": [],
                "query_original": query,
                "query_rewritten": rewritten_query,
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

        combined_context = "\n\n".join(chunks)
        decision = self.grader.grade(rewritten_query, combined_context)

        if decision != "yes":
            return {
                "answer": (
                    "Retrieved notes do not appear relevant. Refine the query or add documents."
                ),
                "sources": source_entries[:3],
                "query_original": query,
                "query_rewritten": rewritten_query,
            }

        answer = self.answerer.generate(rewritten_query, chunks)
        return {
            "answer": answer,
            "sources": source_entries[:3],
            "query_original": query,
            "query_rewritten": rewritten_query,
        }


_pipeline: RAGPipeline | None = None


def get_pipeline(persist_directory: str, top_k: int = 4) -> RAGPipeline:
    global _pipeline
    if _pipeline is None:
        _pipeline = RAGPipeline(persist_directory=persist_directory, top_k=top_k)
    return _pipeline
