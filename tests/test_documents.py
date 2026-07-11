import io

from .conftest import auth_headers, register


def _upload(client, token, filename, text, content_type="text/markdown"):
    return client.post(
        "/api/documents/upload",
        headers=auth_headers(token),
        data={"file": (io.BytesIO(text.encode("utf-8")), filename, content_type)},
        content_type="multipart/form-data",
    )


def test_upload_markdown_and_list(client):
    token, _ = register(client, "uploader@example.com")

    resp = _upload(client, token, "notes.md", "# Notes\nSome markdown content about databases.")
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["chunks_ingested"] >= 1

    resp = client.get("/api/documents", headers=auth_headers(token))
    assert resp.status_code == 200
    docs = resp.get_json()["documents"]
    assert len(docs) == 1
    assert docs[0]["filename"] == "notes.md"
    assert docs[0]["chunk_count"] >= 1


def test_upload_same_content_is_deduplicated(client):
    token, _ = register(client, "dedup@example.com")

    first = _upload(client, token, "a.md", "identical content")
    assert first.status_code == 200
    second = _upload(client, token, "b.md", "identical content")
    assert second.status_code == 200
    assert second.get_json()["message"] == "Document already ingested"


def test_upload_rejects_unsupported_content_type(client):
    token, _ = register(client, "types@example.com")
    resp = _upload(client, token, "img.png", "binary-ish", content_type="image/png")
    assert resp.status_code == 415


def test_upload_sanitizes_filename(client):
    token, _ = register(client, "traversal@example.com")

    resp = _upload(client, token, "../../etc/passwd.md", "# sneaky\npath traversal attempt")
    assert resp.status_code == 200

    resp = client.get("/api/documents", headers=auth_headers(token))
    doc = resp.get_json()["documents"][0]
    assert "/" not in doc["filename"]
    assert ".." not in doc["filename"]
    assert "/" not in doc["stored_name"].split("_", 1)[1]
