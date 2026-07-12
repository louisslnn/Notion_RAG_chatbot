import math


def unique_ordered(values: list[str]) -> list[str]:
    """Deduplicate while keeping the first-occurrence (rank) order."""
    seen: set[str] = set()
    out: list[str] = []
    for value in values:
        if value and value not in seen:
            seen.add(value)
            out.append(value)
    return out


def recall_at_k(expected: list[str], retrieved: list[str], k: int) -> float:
    """Fraction of expected items present in the top-k retrieved items."""
    expected_set = set(expected)
    if not expected_set:
        raise ValueError("recall@k is undefined without expected items")
    top = set(retrieved[:k])
    return len(expected_set & top) / len(expected_set)


def mrr(expected: list[str], retrieved: list[str]) -> float:
    """1 / rank of the first expected item (0 when none is retrieved)."""
    expected_set = set(expected)
    for rank, item in enumerate(retrieved, start=1):
        if item in expected_set:
            return 1.0 / rank
    return 0.0


def ndcg_at_k(expected: list[str], retrieved: list[str], k: int = 5) -> float:
    """Binary-relevance nDCG: rewards ranking expected items first."""
    expected_set = set(expected)
    if not expected_set:
        raise ValueError("nDCG is undefined without expected items")
    dcg = sum(
        1.0 / math.log2(rank + 1)
        for rank, item in enumerate(retrieved[:k], start=1)
        if item in expected_set
    )
    ideal_hits = min(len(expected_set), k)
    idcg = sum(1.0 / math.log2(rank + 1) for rank in range(1, ideal_hits + 1))
    return dcg / idcg


def mean(values: list[float]) -> float:
    return sum(values) / len(values) if values else 0.0
