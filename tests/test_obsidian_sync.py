import shutil
from pathlib import Path

import pytest

from backend.extensions import db
from backend.models import SyncedNote, User
from backend.rag.pipeline import RAGPipeline
from backend.rag.sync import sync_vault

FIXTURE_VAULT = Path(__file__).parent / "fixtures" / "vault"
NOTE_COUNT = 5


@pytest.fixture()
def vault(tmp_path):
    """A writable copy of the fixture vault."""
    target = tmp_path / "vault"
    shutil.copytree(FIXTURE_VAULT, target)
    return target


@pytest.fixture()
def pipeline(tmp_path):
    return RAGPipeline(persist_directory=str(tmp_path / "vs"))


@pytest.fixture()
def user_id(app):
    with app.app_context():
        user = User(email="sync@example.com", password_hash="irrelevant")
        db.session.add(user)
        db.session.commit()
        return user.id


def _chroma_count(pipeline):
    return pipeline._collection_count(pipeline._load_vectorstore())


def _stored_chunk_ids(user_id):
    rows = SyncedNote.query.filter_by(user_id=user_id).all()
    return {row.note_path: list(row.chunk_ids) for row in rows}


def test_initial_sync_ingests_every_note(app, vault, pipeline, user_id):
    with app.app_context():
        report = sync_vault(vault, user_id=user_id, pipeline=pipeline)

        assert len(report.added) == NOTE_COUNT
        assert report.updated == [] and report.deleted == []
        assert SyncedNote.query.filter_by(user_id=user_id).count() == NOTE_COUNT
        # Every chunk in Chroma is accounted for by a SyncedNote row.
        total_ids = sum(len(ids) for ids in _stored_chunk_ids(user_id).values())
        assert _chroma_count(pipeline) == total_ids > 0


def test_second_sync_is_a_noop_without_embedding(app, vault, pipeline, user_id, monkeypatch):
    with app.app_context():
        sync_vault(vault, user_id=user_id, pipeline=pipeline)
        count_before = _chroma_count(pipeline)

        def _no_ingestion(*args, **kwargs):
            pytest.fail("no re-ingestion should happen when the vault is unchanged")

        monkeypatch.setattr(pipeline, "ingest_documents", _no_ingestion)
        monkeypatch.setattr(pipeline, "delete_chunks", _no_ingestion)

        report = sync_vault(vault, user_id=user_id, pipeline=pipeline)

        assert report.unchanged == NOTE_COUNT
        assert report.added == [] and report.updated == [] and report.deleted == []
        assert _chroma_count(pipeline) == count_before


def test_modified_note_replaces_its_old_chunks(app, vault, pipeline, user_id):
    with app.app_context():
        sync_vault(vault, user_id=user_id, pipeline=pipeline)
        old_ids = _stored_chunk_ids(user_id)["Journal.md"]

        journal = vault / "Journal.md"
        journal.write_text(
            journal.read_text(encoding="utf-8") + "\n## 2026-07-03\n\nNouvelle entrée.\n",
            encoding="utf-8",
        )

        report = sync_vault(vault, user_id=user_id, pipeline=pipeline)

        assert report.updated == ["Journal.md"]
        assert report.unchanged == NOTE_COUNT - 1
        new_ids = _stored_chunk_ids(user_id)["Journal.md"]
        assert set(new_ids).isdisjoint(old_ids)
        # Old chunks really left Chroma: the collection matches the tracked ids exactly.
        total_ids = sum(len(ids) for ids in _stored_chunk_ids(user_id).values())
        assert _chroma_count(pipeline) == total_ids


def test_deleted_note_is_purged(app, vault, pipeline, user_id):
    with app.app_context():
        sync_vault(vault, user_id=user_id, pipeline=pipeline)
        removed_ids = _stored_chunk_ids(user_id)["Liens.md"]
        count_before = _chroma_count(pipeline)

        (vault / "Liens.md").unlink()
        report = sync_vault(vault, user_id=user_id, pipeline=pipeline)

        assert report.deleted == ["Liens.md"]
        assert SyncedNote.query.filter_by(user_id=user_id, note_path="Liens.md").count() == 0
        assert _chroma_count(pipeline) == count_before - len(removed_ids)


def test_dry_run_writes_nothing(app, vault, pipeline, user_id):
    with app.app_context():
        report = sync_vault(vault, user_id=user_id, pipeline=pipeline, dry_run=True)

        assert len(report.added) == NOTE_COUNT
        assert SyncedNote.query.filter_by(user_id=user_id).count() == 0
        assert _chroma_count(pipeline) == 0


def test_cli_sync_dry_run(app, vault, user_id):
    with app.app_context():
        email = db.session.get(User, user_id).email

    runner = app.test_cli_runner()
    result = runner.invoke(
        args=["obsidian", "sync", "--vault", str(vault), "--user", email, "--dry-run"]
    )

    assert result.exit_code == 0, result.output
    assert result.output.count("would add:") == NOTE_COUNT
    assert f"{NOTE_COUNT} new, 0 updated, 0 deleted, 0 unchanged" in result.output

    with app.app_context():
        assert SyncedNote.query.filter_by(user_id=user_id).count() == 0


def test_cli_sync_unknown_user(app, vault):
    runner = app.test_cli_runner()
    result = runner.invoke(
        args=["obsidian", "sync", "--vault", str(vault), "--user", "ghost@example.com"]
    )
    assert result.exit_code != 0
    assert "No user found" in result.output
