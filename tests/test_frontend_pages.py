def test_login_page_renders(client):
    r = client.get("/")
    assert r.status_code == 200
    assert b'id="view"' in r.data  # SPA shell mounts every screen here


def test_ride_page_renders(client):
    r = client.get("/ride")
    assert r.status_code == 200
    assert b'id="view"' in r.data


def test_receipt_page_renders(client):
    r = client.get("/receipt")
    assert r.status_code == 200


def test_driver_page_renders(client):
    r = client.get("/driver")
    assert r.status_code == 200


def test_admin_page_renders(client):
    r = client.get("/admin")
    assert r.status_code == 200
