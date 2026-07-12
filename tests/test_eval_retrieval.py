import json
import shutil
from pathlib import Path

from backend.evals.goldset import GoldItem, save_goldset
from backend.evals.retrieval import evaluate_retrieval
from backend.extensions import db
from backend.models import User
from backend.rag.connectors import ObsidianConnector
from backend.rag.ingestion import chunk_markdown
from backend.rag.pipeline import RAGPipeline
from backend.rag.sync import sync_vault

FIXTURE_VAULT = Path(__file__).parent / "fixtures" / "vault"


def _first_chunk_text(note_path: str) -> str:
    docs = {
        doc.metadata["note_path"]: doc for doc in ObsidianConnector(FIXTURE_VAULT).iter_documents()
    }
    doc = docs[note_path]
    chunks = chunk_markdown(doc.content, metadata={})
    return chunks[0].page_content


def _goldset() -> list[GoldItem]:
    # Questions equal to an exact chunk text: with DeterministicFakeEmbedding
    # the query vector matches that chunk's vector, so it must rank first.
    return [
        GoldItem(
            id="q001",
            question=_first_chunk_text("Projet X.md"),
            expected_note_paths=["Projet X.md"],
            expected_answer_points=["point"],
            tags=["factual"],
        ),
        GoldItem(
            id="q002",
            question=_first_chunk_text("Recettes/Tarte aux pommes.md"),
            expected_note_paths=["Recettes/Tarte aux pommes.md"],
            expected_answer_points=["point"],
            tags=["factual"],
        ),
        GoldItem(id="q003", question="Question hors vault ?", tags=["negative"]),
    ]


def _synced_pipeline(app, tmp_path):
    pipeline = RAGPipeline(persist_directory=str(tmp_path / "vs"))
    with app.app_context():
        user = User(email="eval@example.com", password_hash="irrelevant")
        db.session.add(user)
        db.session.commit()
        sync_vault(FIXTURE_VAULT, user_id=user.id, pipeline=pipeline)
        return pipeline, user.id, user.email


def test_eval_retrieval_full_path_on_fixture_vault(app, tmp_path):
    pipeline, user_id, _ = _synced_pipeline(app, tmp_path)

    with app.app_context():
        result = evaluate_retrieval(_goldset(), pipeline=pipeline, user_id=user_id, k=5)

    # Negative question skipped.
    assert result["questions_evaluated"] == 2
    # Identical-text queries must rank their note first.
    assert result["metrics"]["recall@1"] == 1.0
    assert result["metrics"]["mrr"] == 1.0
    assert result["metrics"]["ndcg@5"] == 1.0
    assert "factual" in result["by_tag"]

    detail = {q["id"]: q for q in result["questions"]}
    assert detail["q001"]["retrieved_note_paths"][0] == "Projet X.md"
    assert detail["q002"]["expected_note_paths"] == ["Recettes/Tarte aux pommes.md"]
    assert "q003" not in detail


def test_cli_eval_retrieval_writes_run_file(app, tmp_path, monkeypatch):
    vault_copy = tmp_path / "vault"
    shutil.copytree(FIXTURE_VAULT, vault_copy)

    with app.app_context():
        user = User(email="cli-eval@example.com", password_hash="irrelevant")
        db.session.add(user)
        db.session.commit()
        email = user.email

    goldset_path = tmp_path / "goldset.jsonl"
    save_goldset(_goldset(), goldset_path)
    runs_dir = tmp_path / "runs"

    runner = app.test_cli_runner()
    sync_result = runner.invoke(
        args=["obsidian", "sync", "--vault", str(vault_copy), "--user", email]
    )
    assert sync_result.exit_code == 0, sync_result.output

    result = runner.invoke(
        args=[
            "rag",
            "eval-retrieval",
            "--goldset",
            str(goldset_path),
            "--user",
            email,
            "--runs-dir",
            str(runs_dir),
        ]
    )
    assert result.exit_code == 0, result.output
    assert "recall@1" in result.output

    run_files = list(runs_dir.glob("*.json"))
    assert len(run_files) == 1
    payload = json.loads(run_files[0].read_text(encoding="utf-8"))
    assert payload["run_type"] == "retrieval"
    assert payload["config"]["retrieval"]["final_k"]
    assert "hybrid_enabled" in payload["config"]["retrieval"]
    assert payload["config"]["chunking"]["markdown_max_section_chars"]
    assert len(payload["questions"]) == 2
    assert {"expected_note_paths", "retrieved_note_paths"} <= set(payload["questions"][0])
