from .conftest import auth_headers, register


def test_register_login_me(client):
    token, user_id = register(client, "user@example.com", "a-strong-password")
    assert token

    resp = client.post(
        "/api/auth/login",
        json={"email": "user@example.com", "password": "a-strong-password"},
    )
    assert resp.status_code == 200
    login_token = resp.get_json()["access_token"]

    resp = client.get("/api/auth/me", headers=auth_headers(login_token))
    assert resp.status_code == 200
    user = resp.get_json()["user"]
    assert user["id"] == user_id
    assert user["email"] == "user@example.com"


def test_register_rejects_duplicate_email(client):
    register(client, "dup@example.com")
    resp = client.post(
        "/api/auth/register",
        json={"email": "dup@example.com", "password": "whatever-password"},
    )
    assert resp.status_code == 409


def test_register_requires_email_and_password(client):
    resp = client.post("/api/auth/register", json={"email": "", "password": ""})
    assert resp.status_code == 400


def test_login_rejects_wrong_password(client):
    register(client, "victim@example.com", "correct-password")
    resp = client.post(
        "/api/auth/login",
        json={"email": "victim@example.com", "password": "wrong-password"},
    )
    assert resp.status_code == 401


def test_me_requires_token(client):
    resp = client.get("/api/auth/me")
    assert resp.status_code == 401
