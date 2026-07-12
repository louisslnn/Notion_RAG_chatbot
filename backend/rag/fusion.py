RRF_K = 60


def rrf_fuse(rankings: list[list[str]], k: int = RRF_K) -> dict[str, float]:
    """Reciprocal Rank Fusion: score(item) = sum over lists of 1 / (k + rank).

    Items appearing in several rankings accumulate; ranks are 1-based. k=60 is
    the standard constant from Cormack et al. (2009).
    """
    scores: dict[str, float] = {}
    for ranking in rankings:
        for rank, item in enumerate(ranking, start=1):
            scores[item] = scores.get(item, 0.0) + 1.0 / (k + rank)
    return scores
