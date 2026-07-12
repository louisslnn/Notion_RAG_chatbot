import math
import os

RERANKER_MODEL_NAME = os.getenv("RERANKER_MODEL_NAME", "BAAI/bge-reranker-v2-m3")


class Reranker:
    """Cross-encoder reranker, loaded lazily and cached like the embedding model."""

    def __init__(self, model_name: str = RERANKER_MODEL_NAME):
        self.model_name = model_name
        self._model = None

    @property
    def model(self):
        if self._model is None:
            from sentence_transformers import CrossEncoder

            self._model = CrossEncoder(self.model_name)
        return self._model

    def score(self, query: str, texts: list[str]) -> list[float]:
        """Sigmoid-normalized relevance scores in [0, 1], one per text."""
        raw = self.model.predict([(query, text) for text in texts])
        return [1.0 / (1.0 + math.exp(-float(score))) for score in raw]
