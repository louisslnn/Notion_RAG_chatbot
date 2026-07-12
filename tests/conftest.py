import pytest
from langchain_core.embeddings import DeterministicFakeEmbedding

from backend.app import create_app
from backend.config import BaseConfig
from backend.extensions import db
from backend.rag import pipeline as pipeline_module


class FakeAnswerer:
    def generate(self, question, chunks):
        return f"Answer based on {len(chunks)} chunk(s)."


class FakeRewriter:
    def rewrite(self, original_query):
        return original_query

    def condense(self, question, history):
        return question


class FakeReranker:
    """High constant relevance: never triggers the rerank threshold."""

    def score(self, query, texts):
        return [0.9] * len(texts)


@pytest.fixture(autouse=True)
def _patch_rag(monkeypatch):
    """Replace embeddings and LLM components with deterministic fakes.

    RAGPipeline instantiates these by name from its own module, so patching the
    module attributes is enough — no network access or API key required.
    """
    monkeypatch.setattr(
        pipeline_module,
        "HuggingFaceEmbeddings",
        lambda **kwargs: DeterministicFakeEmbedding(size=64),
    )
    monkeypatch.setattr(pipeline_module, "AnswerGenerator", FakeAnswerer)
    monkeypatch.setattr(pipeline_module, "QueryRewriter", FakeRewriter)
    monkeypatch.setattr(pipeline_module, "Reranker", FakeReranker)
    pipeline_module._pipeline = None
    yield
    pipeline_module._pipeline = None


@pytest.fixture()
def app(tmp_path):
    class TestConfig(BaseConfig):
        TESTING = True
        SQLALCHEMY_DATABASE_URI = "sqlite://"
        JWT_SECRET_KEY = "test-secret-key-long-enough-for-hs256-signing"
        UPLOAD_FOLDER = str(tmp_path / "uploads")
        VECTOR_STORE_FOLDER = str(tmp_path / "vectorstore")
        RATELIMIT_ENABLED = False

    flask_app = create_app(TestConfig)
    yield flask_app
    with flask_app.app_context():
        db.session.remove()
        db.drop_all()


@pytest.fixture()
def client(app):
    return app.test_client()


def register(client, email, password="s3cret-password"):
    resp = client.post("/api/auth/register", json={"email": email, "password": password})
    assert resp.status_code == 200, resp.get_json()
    data = resp.get_json()
    return data["access_token"], data["user"]["id"]


def auth_headers(token):
    return {"Authorization": f"Bearer {token}"}
