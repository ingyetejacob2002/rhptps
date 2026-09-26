from tests.conftest import register_and_login, auth_header


def _create_ride_and_capture_setup(client):
    rider = register_and_login(client, role="rider", email="r1@example.com")
    driver = register_and_login(
        client, role="driver", email="d1@example.com",
        bank_account_number="0123456789", vehicle_reg_number="ABC123XY",
    )

    r = client.post(
        "/api/rides",
        json={
            "driver_id": driver["id"],
            "distance_km": 7.4,
            "duration_minutes": 18,
            "pickup_location": "Wurukum",
            "dropoff_location": "North Bank",
            "payment_method": "card",
        },
        headers=auth_header(rider["access"]),
    )
    assert r.status_code == 201, r.get_json()
    return rider, driver, r.get_json()


def test_capture_succeeds_and_generates_receipt(client):
    rider, driver, ride = _create_ride_and_capture_setup(client)

    r = client.post(
        f"/api/payments/{ride['ride_id']}/capture",
        json={"idempotency_key": "idem-key-001"},
        headers=auth_header(rider["access"]),
    )
    assert r.status_code == 201
    body = r.get_json()
    assert body["status"] == "success"

    receipt = client.get(
        f"/api/receipts/{body['transaction_id']}", headers=auth_header(rider["access"])
    )
    assert receipt.status_code == 200
    assert receipt.get_json()["reference"] == "idem-key-001"


def test_retry_with_same_idempotency_key_does_not_duplicate(client):
    rider, driver, ride = _create_ride_and_capture_setup(client)

    first = client.post(
        f"/api/payments/{ride['ride_id']}/capture",
        json={"idempotency_key": "idem-key-002"},
        headers=auth_header(rider["access"]),
    )
    second = client.post(
        f"/api/payments/{ride['ride_id']}/capture",
        json={"idempotency_key": "idem-key-002"},
        headers=auth_header(rider["access"]),
    )
    assert first.get_json()["transaction_id"] == second.get_json()["transaction_id"]

    history = client.get("/api/transactions", headers=auth_header(rider["access"]))
    ride_txns = [t for t in history.get_json() if t["payment_id"] == first.get_json()["payment_id"]]
    assert len(ride_txns) == 1  # no duplicate row created


def test_capture_missing_idempotency_key_rejected(client):
    rider, driver, ride = _create_ride_and_capture_setup(client)
    r = client.post(
        f"/api/payments/{ride['ride_id']}/capture",
        json={},
        headers=auth_header(rider["access"]),
    )
    assert r.status_code == 400
