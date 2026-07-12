import io
import json
import re

from .conftest import auth_headers, register


def _upload(client, token, filename, text):
    resp = client.post(
        "/api/documents/upload",
        headers=auth_headers(token),
        data={"file": (io.BytesIO(text.encode("utf-8")), filename, "text/markdown")},
        content_type="multipart/form-data",
    )
    assert resp.status_code == 200, resp.get_json()


def _parse_sse(body: str) -> list[tuple[str, dict]]:
    events = []
    for frame in body.split("\n\n"):
        match = re.search(r"^event: (\S+)\ndata: (.*)$", frame.strip(), re.S)
        if match:
            events.append((match.group(1), json.loads(match.group(2))))
    return events


def test_stream_route_emits_sources_then_deltas_then_done(client):
    token, _ = register(client, "sse@example.com")
    _upload(client, token, "notes.md", "# Notes\nLe backend du projet utilise Flask.")

    resp = client.post(
        "/api/chat/query/stream",
        headers=auth_headers(token),
        json={"message": "Quel framework backend utilise le projet selon mes notes ?"},
    )
    assert resp.status_code == 200
    assert resp.mimetype == "text/event-stream"

    events = _parse_sse(resp.get_data(as_text=True))
    names = [name for name, _ in events]

    assert names[0] == "sources"
    assert names[-1] == "done"
    assert set(names[1:-1]) == {"delta"}

    sources_payload = events[0][1]
    assert sources_payload["sources"], "sources should arrive before the answer"
    # Public sources never expose the full chunk content.
    assert all("content" not in src for src in sources_payload["sources"])

    answer = "".join(data["text"] for name, data in events if name == "delta")
    assert answer.startswith("Answer based on")

    done = events[-1][1]
    assert done["session_id"]
    assert done["latency_ms"] >= 0


def test_stream_route_persists_messages_at_the_end(client):
    token, _ = register(client, "sse-db@example.com")
    _upload(client, token, "notes.md", "# Notes\nContenu de test pour la persistance.")

    resp = client.post(
        "/api/chat/query/stream",
        headers=auth_headers(token),
        json={"message": "Que disent mes notes sur la persistance exactement ?"},
    )
    events = _parse_sse(resp.get_data(as_text=True))
    session_id = events[-1][1]["session_id"]
    answer = "".join(data["text"] for name, data in events if name == "delta")

    history = client.get("/api/chat/history", headers=auth_headers(token)).get_json()
    session = next(s for s in history["sessions"] if s["session_id"] == session_id)
    roles = [message["role"] for message in session["messages"]]
    assert roles == ["user", "assistant"]
    assert session["messages"][1]["content"] == answer
    assert session["messages"][1]["sources"]


def test_stream_route_requires_message(client):
    token, _ = register(client, "sse-empty@example.com")
    resp = client.post(
        "/api/chat/query/stream", headers=auth_headers(token), json={"message": "  "}
    )
    assert resp.status_code == 400
