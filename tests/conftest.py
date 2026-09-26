import pytest

from app import create_app
from app.config import TestConfig
from app.extensions import db


@pytest.fixture()
def app():
    app = create_app(TestConfig)
    with app.app_context():
        db.create_all()
        yield app
        db.session.remove()
        db.drop_all()


@pytest.fixture()
def client(app):
    return app.test_client()


def register_and_login(client, role="rider", email="rider@example.com", **extra):
    payload = {
        "role": role,
        "full_name": "Test User",
        "email": email,
        "phone_number": "08012345678",
        "password": "supersecret1",
    }
    payload.update(extra)
    r = client.post("/api/auth/register", json=payload)
    assert r.status_code == 201, r.get_json()

    r = client.post("/api/auth/login", json={"email": email, "password": "supersecret1"})
    assert r.status_code == 200, r.get_json()
    return r.get_json()


def auth_header(token):
    return {"Authorization": f"Bearer {token}"}
