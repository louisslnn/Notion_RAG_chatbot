import os
from dataclasses import dataclass

REWRITE_MODES = ("always", "auto", "never")


def _env_bool(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in ("1", "true", "yes", "on")


def _env_int(name: str, default: int) -> int:
    raw = os.getenv(name)
    return int(raw) if raw else default


def _env_float(name: str, default: float) -> float:
    raw = os.getenv(name)
    return float(raw) if raw else default


@dataclass(frozen=True)
class RetrievalConfig:
    """Every retrieval feature flag, so eval runs can snapshot and ablate them."""

    hybrid_enabled: bool = False
    rerank_enabled: bool = False
    rewrite_mode: str = "auto"
    candidate_k: int = 20
    final_k: int = 5
    # Sigmoid-normalized cross-encoder relevance below which a chunk is
    # considered irrelevant. Only applied when rerank_enabled.
    rerank_threshold: float = 0.3
    # Number of past chat messages passed to query() as history.
    history_window: int = 6

    def __post_init__(self):
        if self.rewrite_mode not in REWRITE_MODES:
            raise ValueError(f"rewrite_mode must be one of {REWRITE_MODES}")

    @classmethod
    def from_env(cls) -> "RetrievalConfig":
        return cls(
            hybrid_enabled=_env_bool("RETRIEVAL_HYBRID", cls.hybrid_enabled),
            rerank_enabled=_env_bool("RETRIEVAL_RERANK", cls.rerank_enabled),
            rewrite_mode=os.getenv("REWRITE_MODE", cls.rewrite_mode),
            candidate_k=_env_int("RETRIEVAL_CANDIDATE_K", cls.candidate_k),
            final_k=_env_int("RETRIEVAL_FINAL_K", cls.final_k),
            rerank_threshold=_env_float("RERANK_THRESHOLD", cls.rerank_threshold),
            history_window=_env_int("CHAT_HISTORY_WINDOW", cls.history_window),
        )
