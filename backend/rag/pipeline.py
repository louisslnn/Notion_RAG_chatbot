import json
import os
from pathlib import Path
from threading import RLock
from typing import Dict, Iterable, List, Optional

from langchain_core.documents import Document
from langchain_community.embeddings import HuggingFaceEmbeddings
from langchain_community.vectorstores import Chroma

from .answerer import AnswerGenerator
from .grader import ContextGrader
from .ingestion import documents_from_texts, chunk_text, hash_content
from .rewriter import QueryRewriter

EMBEDDING_MODEL_NAME = os.getenv("EMBEDDING_MODEL_NAME", "sentence-transformers/all-MiniLM-L6-v2")


class RAGPipeline:
    def __init__(self, persist_directory: str, top_k: int = 4):
        self.persist_directory = Path(persist_directory)
        self.top_k = top_k
        self._lock = RLock()
        self._vectorstore: Optional[Chroma] = None
        self.embedding = HuggingFaceEmbeddings(model_name=EMBEDDING_MODEL_NAME)
        self.answerer = AnswerGenerator()
        self.grader = ContextGrader()
        self.rewriter = QueryRewriter()

        self.persist_directory.mkdir(parents=True, exist_ok=True)

    def _load_vectorstore(self) -> Chroma:
        if self._vectorstore is None:
            self._vectorstore = Chroma(
                embedding_function=self.embedding,
                persist_directory=str(self.persist_directory),
            )
        return self._vectorstore

    def _persist(self):
        if self._vectorstore:
            self._vectorstore.persist()

    def ingest_documents(self, docs: List[Document]) -> int:
        if not docs:
            return 0
        with self._lock:
            vectorstore = self._load_vectorstore()
            vectorstore.add_documents(docs)
            self._persist()
        return len(docs)

    def ingest_texts(self, texts: Iterable[str], base_metadata: Optional[Dict] = None) -> int:
        docs = documents_from_texts(texts, base_metadata=base_metadata)
        return self.ingest_documents(docs)

    def ingest_uploaded_text(self, content: str, metadata: Optional[Dict] = None) -> Dict[str, int]:
        docs = chunk_text(content, metadata=metadata)
        added = self.ingest_documents(docs)
        return {"chunks_added": added, "content_hash": hash_content(content)}

    def query(self, query: str, *, top_k: Optional[int] = None) -> Dict:
        vectorstore = self._load_vectorstore()
        if vectorstore._collection.count() == 0:  # type: ignore[attr-defined]
            return {
                "answer": "Knowledge base is empty. Upload documents or sync Notion to get started.",
                "sources": [],
                "query_original": query,
            }

        rewritten_query = self.rewriter.rewrite(query)
        k = top_k or self.top_k
        results = vectorstore.similarity_search_with_relevance_scores(rewritten_query, k=k)

        if not results:
            return {
                "answer": "No relevant documents were found for the query.",
                "sources": [],
                "query_original": query,
                "query_rewritten": rewritten_query,
            }

        chunks = []
        source_entries = []
        for doc, score in results[: max(3, k)]:
            chunks.append(doc.page_content)
            confidence = min(1.0, max(0.0, float(score)))
            source_entries.append(
                {
                    "source": doc.metadata.get("source", "unknown"),
                    "score": score,
                    "confidence": round(confidence, 3),
                    "metadata": doc.metadata,
                    "snippet": doc.page_content[:280] + ("..." if len(doc.page_content) > 280 else ""),
                }
            )

        combined_context = "\n\n".join(chunks)
        decision = self.grader.grade(rewritten_query, combined_context)

        if decision != "yes":
            return {
                "answer": "Retrieved notes do not appear relevant. Refine the query or add documents.",
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


_pipeline: Optional[RAGPipeline] = None


def get_pipeline(persist_directory: str, top_k: int = 4) -> RAGPipeline:
    global _pipeline
    if _pipeline is None:
        _pipeline = RAGPipeline(persist_directory=persist_directory, top_k=top_k)
    return _pipeline

