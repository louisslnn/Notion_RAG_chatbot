import io

import pytest

from backend.rag.pipeline import RAGPipeline

from .conftest import auth_headers, register


def upload_markdown(client, token, filename, text):
    resp = client.post(
        "/api/documents/upload",
        headers=auth_headers(token),
        data={"file": (io.BytesIO(text.encode("utf-8")), filename, "text/markdown")},
        content_type="multipart/form-data",
    )
    assert resp.status_code == 200, resp.get_json()
    return resp.get_json()


def test_pipeline_query_filters_by_user(tmp_path):
    pipeline = RAGPipeline(persist_directory=str(tmp_path / "vs"))
    pipeline.ingest_uploaded_text(
        "Alice keeps notes about quantum llamas and orbital gardening.",
        metadata={"source": "alice.md", "user_id": 1},
    )
    pipeline.ingest_uploaded_text(
        "Bob keeps notes about quantum llamas and deep sea mining.",
        metadata={"source": "bob.md", "user_id": 2},
    )

    result = pipeline.query("quantum llamas", user_id=1)

    assert result["sources"], "user 1 should retrieve their own document"
    assert all(src["metadata"]["user_id"] == 1 for src in result["sources"])
    assert all(src["source"] == "alice.md" for src in result["sources"])


def test_ingestion_rejects_documents_without_user_id(tmp_path):
    pipeline = RAGPipeline(persist_directory=str(tmp_path / "vs"))
    with pytest.raises(ValueError, match="user_id"):
        pipeline.ingest_uploaded_text("orphan note", metadata={"source": "orphan.md"})


def test_users_only_retrieve_their_own_documents(client):
    token_a, user_a = register(client, "alice@example.com")
    token_b, user_b = register(client, "bob@example.com")

    upload_markdown(
        client, token_a, "alice.md", "# Alice\nAlice's secret project is codenamed AQUILA."
    )
    upload_markdown(client, token_b, "bob.md", "# Bob\nBob's secret project is codenamed BOREAL.")

    for token, own_user_id, own_code, other_code in (
        (token_a, user_a, "AQUILA", "BOREAL"),
        (token_b, user_b, "BOREAL", "AQUILA"),
    ):
        resp = client.post(
            "/api/chat/query",
            headers=auth_headers(token),
            json={"message": "What is the secret project codename?"},
        )
        assert resp.status_code == 200, resp.get_json()
        sources = resp.get_json()["sources"]
        assert sources, "each user should retrieve their own document"
        assert all(src["metadata"]["user_id"] == own_user_id for src in sources)
        assert any(own_code in src["snippet"] for src in sources)
        assert all(other_code not in src["snippet"] for src in sources)
