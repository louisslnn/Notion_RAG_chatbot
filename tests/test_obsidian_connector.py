from pathlib import Path

from backend.rag.connectors import ObsidianConnector

FIXTURE_VAULT = Path(__file__).parent / "fixtures" / "vault"


def _documents():
    return {
        doc.metadata["note_path"]: doc for doc in ObsidianConnector(FIXTURE_VAULT).iter_documents()
    }


def test_vault_scan_skips_hidden_and_trash_directories():
    docs = _documents()
    assert set(docs) == {
        "Projet X.md",
        "Journal.md",
        "Liens.md",
        "Schéma.md",
        "Recettes/Tarte aux pommes.md",
    }


def test_parse_note_frontmatter_tags_outlinks_and_content():
    doc = _documents()["Projet X.md"]

    # Frontmatter fields are injected as metadata; the body has no frontmatter left.
    assert doc.metadata["status"] == "en cours"
    assert doc.metadata["aliases"] == ["PX"]
    assert "status:" not in doc.content
    assert doc.content.startswith("# Projet X")

    # Frontmatter tags merged with inline tags (incl. nested), deduplicated.
    assert doc.metadata["tags"] == ["projet", "actif", "important", "dev/python"]

    # Wikilinks collected as outlinks (alias and #heading forms included)...
    assert doc.metadata["outlinks"] == ["Roadmap 2026", "Infra"]
    # ...and their text stays in the content, without brackets.
    assert "la roadmap" in doc.content
    assert "Infra > Réseau" in doc.content
    assert "[[" not in doc.content


def test_systematic_metadata():
    doc = _documents()["Recettes/Tarte aux pommes.md"]
    assert doc.metadata["note_title"] == "Tarte aux pommes"
    assert doc.metadata["folder"] == "Recettes"
    assert doc.metadata["modified_at"]  # ISO mtime

    root_doc = _documents()["Journal.md"]
    assert root_doc.metadata["folder"] == ""


def test_image_embeds_are_stripped():
    doc = _documents()["Schéma.md"]
    assert "diagram.png" not in doc.content
    assert "![[" not in doc.content
    assert "Fin de la note." in doc.content


def test_inline_nested_tags_without_frontmatter():
    doc = _documents()["Journal.md"]
    assert "journal/quotidien" in doc.metadata["tags"]
    assert "reunion" in doc.metadata["tags"]
    assert doc.metadata["outlinks"] == ["Projet X"]
