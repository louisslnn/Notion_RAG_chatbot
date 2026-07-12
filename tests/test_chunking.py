from backend.rag.ingestion import MAX_SECTION_CHARS, chunk_content, chunk_markdown

NESTED_MARKDOWN = """# Projet X

Introduction.

## Architecture

Vue d'ensemble.

### Backend

Le backend est en Flask.

## Notes

Autre section.
"""


def test_heading_path_follows_markdown_structure():
    docs = chunk_markdown(NESTED_MARKDOWN, {"source": "x.md"})
    by_heading = {doc.metadata.get("heading_path"): doc.page_content for doc in docs}

    assert "Le backend est en Flask." in by_heading["Projet X > Architecture > Backend"]
    assert "Vue d'ensemble." in by_heading["Projet X > Architecture"]
    assert "Autre section." in by_heading["Projet X > Notes"]
    # Base metadata is inherited by every chunk.
    assert all(doc.metadata["source"] == "x.md" for doc in docs)


def test_oversized_section_is_subsplit_and_inherits_heading_path():
    big_section = "# Titre\n\n## Longue section\n\n" + ("phrase de remplissage. " * 400)
    docs = chunk_markdown(big_section, {"source": "big.md"})

    long_chunks = [d for d in docs if d.metadata.get("heading_path") == "Titre > Longue section"]
    assert len(long_chunks) > 1
    assert all(len(d.page_content) <= MAX_SECTION_CHARS for d in long_chunks)


def test_chunk_content_dispatches_on_markdown():
    md_docs = chunk_content("# T\n\ncorps", content_type="text/markdown")
    assert md_docs[0].metadata.get("heading_path") == "T"

    md_by_extension = chunk_content("# T\n\ncorps", metadata={"source": "note.md"})
    assert md_by_extension[0].metadata.get("heading_path") == "T"

    txt_docs = chunk_content("# pas du markdown", content_type="text/plain")
    assert "heading_path" not in txt_docs[0].metadata
