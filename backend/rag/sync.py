import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from uuid import uuid4

from ..extensions import db
from ..models import SyncedNote
from .connectors import ObsidianConnector
from .ingestion import chunk_markdown, hash_content
from .pipeline import RAGPipeline


@dataclass
class SyncReport:
    added: list[str] = field(default_factory=list)
    updated: list[str] = field(default_factory=list)
    deleted: list[str] = field(default_factory=list)
    unchanged: int = 0
    duration_seconds: float = 0.0


def sync_vault(
    vault_path: str | Path,
    *,
    user_id: int,
    pipeline: RAGPipeline,
    dry_run: bool = False,
) -> SyncReport:
    """Incrementally sync an Obsidian vault into the user's knowledge base.

    Unchanged notes (same content hash) are skipped without any embedding
    call, modified notes have their previous chunks deleted from Chroma
    before re-ingestion, and notes that disappeared from the vault are
    purged. With dry_run=True nothing is written anywhere.
    """
    started = time.perf_counter()
    report = SyncReport()
    connector = ObsidianConnector(vault_path)

    stale = {row.note_path: row for row in SyncedNote.query.filter_by(user_id=user_id)}

    for doc in connector.iter_documents():
        note_path = doc.metadata["note_path"]
        content_hash = hash_content(doc.content)
        record = stale.pop(note_path, None)

        if record and record.content_hash == content_hash:
            report.unchanged += 1
            continue

        (report.updated if record else report.added).append(note_path)
        if dry_run:
            continue

        metadata = {**doc.metadata, "user_id": user_id, "source": note_path}
        chunks = chunk_markdown(doc.content, metadata=metadata)
        chunk_ids = [str(uuid4()) for _ in chunks]

        if record:
            pipeline.delete_chunks(record.chunk_ids or [])
        if chunks:
            pipeline.ingest_documents(chunks, ids=chunk_ids)

        if record:
            record.content_hash = content_hash
            record.chunk_ids = chunk_ids
            record.last_synced_at = datetime.utcnow()
        else:
            db.session.add(
                SyncedNote(
                    user_id=user_id,
                    note_path=note_path,
                    content_hash=content_hash,
                    chunk_ids=chunk_ids,
                    last_synced_at=datetime.utcnow(),
                )
            )

    for note_path, record in stale.items():
        report.deleted.append(note_path)
        if dry_run:
            continue
        pipeline.delete_chunks(record.chunk_ids or [])
        db.session.delete(record)

    if not dry_run:
        db.session.commit()

    report.duration_seconds = time.perf_counter() - started
    return report
