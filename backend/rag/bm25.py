import re
from dataclasses import dataclass

from rank_bm25 import BM25Okapi

_TOKEN_RE = re.compile(r"\w+", re.UNICODE)


def tokenize(text: str) -> list[str]:
    return _TOKEN_RE.findall(text.lower())


@dataclass
class BM25Hit:
    chunk_id: str
    content: str
    metadata: dict
    rank: int  # 1-based


class UserBM25Index:
    """BM25 index over one user's chunks (mirrors the Chroma user filter)."""

    def __init__(self, ids: list[str], contents: list[str], metadatas: list[dict]):
        self.ids = ids
        self.contents = contents
        self.metadatas = metadatas
        self._bm25 = BM25Okapi([tokenize(text) for text in contents]) if contents else None

    def search(self, query: str, k: int) -> list[BM25Hit]:
        if self._bm25 is None:
            return []
        scores = self._bm25.get_scores(tokenize(query))
        order = sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)
        hits: list[BM25Hit] = []
        for index in order[:k]:
            if scores[index] <= 0:
                break  # no lexical overlap at all: not a match
            hits.append(
                BM25Hit(
                    chunk_id=self.ids[index],
                    content=self.contents[index],
                    metadata=self.metadatas[index] or {},
                    rank=len(hits) + 1,
                )
            )
        return hits
