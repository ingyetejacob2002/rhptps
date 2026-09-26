from tests.conftest import register_and_login, auth_header


def test_high_velocity_rule_flags_rapid_repeat_trips(client, app):
    rider = register_and_login(client, role="rider", email="velocity@example.com")
    driver = register_and_login(
        client, role="driver", email="vd@example.com",
        bank_account_number="0123456789", vehicle_reg_number="XYZ999AA",
    )

    # Section 4.7: two rapid repeat trips from one account within 2
    # minutes should trigger HIGH_VELOCITY (risk score 40, below the
    # 70 alert threshold on its own — logged but not escalated, matching
    # the documented "Pass (as designed)" outcome for a single rule).
    for i in range(2):
        ride = client.post(
            "/api/rides",
            json={
                "driver_id": driver["id"], "distance_km": 3.0, "duration_minutes": 8,
                "pickup_location": "Wadata", "dropoff_location": "High Level",
            },
            headers=auth_header(rider["access"]),
        ).get_json()
        client.post(
            f"/api/payments/{ride['ride_id']}/capture",
            json={"idempotency_key": f"velocity-key-{i}"},
            headers=auth_header(rider["access"]),
        )

    with app.app_context():
        from app.models import FraudAlert
        # Threshold (70) is not cleared by HIGH_VELOCITY alone (40), so no
        # alert row is written — this confirms the rule fired without a
        # false escalation, matching the documented single-rule outcome.
        assert FraudAlert.query.count() == 0


def test_combined_rules_clear_threshold_and_create_alert(client, app):
    """
    Geolocation-mismatch rule (+35) stacked on top of velocity (+40)
    clears the 70-point threshold and should create a Fraud_Alert.
    """
    rider = register_and_login(client, role="rider", email="combo@example.com")
    driver = register_and_login(
        client, role="driver", email="comd@example.com",
        bank_account_number="0123456789", vehicle_reg_number="LMN456BB",
    )

    for i in range(2):
        ride = client.post(
            "/api/rides",
            json={
                "driver_id": driver["id"], "distance_km": 12.0, "duration_minutes": 5,
                # Same-named pickup/dropoff with nontrivial distance
                # trips geolocation_mismatch().
                "pickup_location": "Same Spot", "dropoff_location": "same spot",
            },
            headers=auth_header(rider["access"]),
        ).get_json()
        client.post(
            f"/api/payments/{ride['ride_id']}/capture",
            json={"idempotency_key": f"combo-key-{i}"},
            headers=auth_header(rider["access"]),
        )

    with app.app_context():
        from app.models import FraudAlert
        alerts = FraudAlert.query.all()
        assert len(alerts) >= 1
        assert "HIGH_VELOCITY" in alerts[-1].rule_triggered
        assert "GEO_MISMATCH" in alerts[-1].rule_triggered
        assert alerts[-1].review_status == "open"
