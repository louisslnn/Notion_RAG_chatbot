import pytest

from backend.evals.metrics import unique_ordered
from backend.rag.fusion import rrf_fuse


def test_rrf_hand_computed():
    # Dense ranking: [A, B]; BM25 ranking: [B, C]; k = 60.
    scores = rrf_fuse([["A", "B"], ["B", "C"]], k=60)

    assert scores["A"] == pytest.approx(1 / 61)
    assert scores["B"] == pytest.approx(1 / 62 + 1 / 61)
    assert scores["C"] == pytest.approx(1 / 62)

    ranked = sorted(scores, key=scores.get, reverse=True)
    assert ranked == ["B", "A", "C"]


def test_rrf_single_ranking_preserves_order():
    scores = rrf_fuse([["A", "B", "C"]])
    assert scores["A"] > scores["B"] > scores["C"]


def test_rrf_empty():
    assert rrf_fuse([]) == {}
    assert unique_ordered([]) == []
