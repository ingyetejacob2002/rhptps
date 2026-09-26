from app.fare import compute_fare


def test_fare_matches_worked_example(app):
    # Section 4.7's test table states this trip's fare as N1,196.00, but
    # 200 + (7.4*90) + (18*15) = 1136.00 — that figure in the document
    # is an arithmetic error (flagged separately), not a bug here.
    with app.app_context():
        fare = compute_fare(distance_km=7.4, duration_minutes=18)
        assert fare == 1136.00


def test_fare_never_falls_below_base_fare(app):
    with app.app_context():
        fare = compute_fare(distance_km=0, duration_minutes=0, promo_discount=9999)
        assert fare == app.config["BASE_FARE"]


def test_surge_multiplier_increases_fare(app):
    with app.app_context():
        base = compute_fare(distance_km=5, duration_minutes=10)
        surged = compute_fare(distance_km=5, duration_minutes=10, surge_multiplier=1.5)
        assert surged > base
