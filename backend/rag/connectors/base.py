from abc import ABC, abstractmethod
from collections.abc import Iterator
from dataclasses import dataclass, field


@dataclass
class SourceDocument:
    """A single document produced by a source connector, before chunking."""

    content: str
    metadata: dict = field(default_factory=dict)


class SourceConnector(ABC):
    """A source of documents to ingest (Obsidian vault, Notion workspace, ...)."""

    @abstractmethod
    def iter_documents(self) -> Iterator[SourceDocument]:
        """Yield every document exposed by this source."""
