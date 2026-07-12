import pytest

from backend.evals.metrics import mrr, ndcg_at_k, recall_at_k, unique_ordered


def test_unique_ordered_keeps_rank_order_and_drops_empties():
    assert unique_ordered(["a", "b", "a", "", "c", "b"]) == ["a", "b", "c"]


def test_recall_at_k_hand_computed():
    expected = ["A", "B"]
    # A found at rank 1, B never retrieved.
    assert recall_at_k(expected, ["A", "C", "D"], 1) == 0.5
    assert recall_at_k(expected, ["A", "C", "D"], 3) == 0.5
    # Nothing in top-1, both found within top-3.
    assert recall_at_k(expected, ["C", "A", "B"], 1) == 0.0
    assert recall_at_k(expected, ["C", "A", "B"], 3) == 1.0


def test_recall_requires_expected_items():
    with pytest.raises(ValueError):
        recall_at_k([], ["A"], 3)


def test_mrr_hand_computed():
    assert mrr(["B"], ["B", "C"]) == 1.0
    assert mrr(["B"], ["C", "B"]) == 0.5
    assert mrr(["B"], ["C", "D", "E", "B"]) == 0.25
    assert mrr(["B"], ["C", "D"]) == 0.0


def test_ndcg_hand_computed():
    # Perfect ranking: expected notes occupy the first ranks -> 1.0.
    assert ndcg_at_k(["A", "B"], ["A", "B", "C"], 5) == pytest.approx(1.0)
    # Single expected note at rank 2: DCG = 1/log2(3), IDCG = 1/log2(2) = 1.
    assert ndcg_at_k(["A"], ["X", "A"], 5) == pytest.approx(0.6309, abs=1e-4)
    # Two expected, only one found at rank 2:
    # DCG = 1/log2(3) = 0.6309; IDCG = 1 + 1/log2(3) = 1.6309.
    assert ndcg_at_k(["A", "B"], ["X", "A", "Y"], 5) == pytest.approx(0.3869, abs=1e-4)
    # Expected note beyond the cutoff counts as a miss.
    assert ndcg_at_k(["A"], ["1", "2", "3", "4", "5", "A"], 5) == 0.0
