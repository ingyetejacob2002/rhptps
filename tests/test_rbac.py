from tests.conftest import register_and_login, auth_header


def test_rider_denied_admin_fraud_alerts(client):
    rider = register_and_login(client, role="rider", email="rbac-rider@example.com")
    r = client.get("/api/admin/fraud-alerts", headers=auth_header(rider["access"]))
    assert r.status_code == 403


def test_unauthenticated_request_rejected(client):
    r = client.get("/api/admin/fraud-alerts")
    assert r.status_code == 401


def test_admin_can_access_fraud_alerts(client):
    # Admins aren't self-registered via /api/auth/register (no public
    # admin signup, Section 4.5 access column) — seed one directly.
    from app.models import Admin
    from app.extensions import db

    admin = Admin(full_name="Ada Admin", email="admin@example.com", role_level="super-admin")
    admin.set_password("adminpass1")
    db.session.add(admin)
    db.session.commit()

    r = client.post("/api/auth/login", json={"email": "admin@example.com", "password": "adminpass1"})
    assert r.status_code == 200
    token = r.get_json()["access"]

    r = client.get("/api/admin/fraud-alerts", headers=auth_header(token))
    assert r.status_code == 200


def test_login_with_wrong_password_rejected(client):
    register_and_login(client, role="rider", email="wrongpw@example.com")
    r = client.post("/api/auth/login", json={"email": "wrongpw@example.com", "password": "wrongone"})
    assert r.status_code == 401
