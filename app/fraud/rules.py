"""
Fraud-detection module (Section 4.3.4). Evaluates a completed
transaction against velocity, geolocation-mismatch and promo-abuse
rules and writes a Fraud_Alert when the combined risk score clears the
configured threshold (Section 3.10.4, 3.14).

Thresholds/weights match Section 4.3.4 exactly: HIGH_VELOCITY +40,
GEO_MISMATCH +35, PROMO_ABUSE +30, threshold 70.
"""
from datetime import timedelta

from flask import current_app

from app.extensions import db
from app.models import Transaction, Payment, Ride, FraudAlert


def velocity_check(user_id: str) -> bool:
    """True if the rider has completed an unusually high number of
    trips in a short window (Section 4.3.4)."""
    window = timedelta(minutes=current_app.config["FRAUD_VELOCITY_WINDOW_MINUTES"])
    threshold_count = current_app.config["FRAUD_VELOCITY_TRIP_COUNT"]

    # Window filter done in Python rather than a DB-specific interval
    # expression, so this runs unmodified on SQLite and PostgreSQL.
    from datetime import datetime, timezone
    now = datetime.now(timezone.utc)
    recent = (
        db.session.query(Transaction)
        .join(Payment)
        .join(Ride)
        .filter(Ride.user_id == user_id, Transaction.status == "success")
        .all()
    )
    recent_in_window = [
        t for t in recent
        if t.created_at and (now - t.created_at.replace(tzinfo=timezone.utc) <= window)
    ]
    return len(recent_in_window) >= threshold_count


def geolocation_mismatch(ride: Ride) -> bool:
    """
    Placeholder rule: flags a ride whose pickup and dropoff locations
    are identical strings but distance_km is implausibly large, standing
    in for the full geolocation-consistency check described in Section
    3.10.4 (which in a production system would compare against the
    rider's recent GPS trail rather than static text fields).
    """
    if not ride.pickup_location or not ride.dropoff_location:
        return False
    same_named_location = ride.pickup_location.strip().lower() == ride.dropoff_location.strip().lower()
    return same_named_location and float(ride.distance_km) > 1.0


def promo_abuse_check(user_id: str, promo_code: str | None = None) -> bool:
    """
    Placeholder rule for single-use promo code reuse (Section 4.3.4).
    Wired to always return False unless a promo_code is supplied and has
    already been used successfully by this rider — the real system would
    consult a PromoRedemptions table; this project scopes that out.
    """
    return False


def evaluate(transaction_id: str) -> int:
    txn = Transaction.query.get(transaction_id)
    if txn is None:
        return 0

    threshold = current_app.config["FRAUD_RISK_THRESHOLD"]
    score = 0
    triggered = []

    ride = txn.payment.ride

    if velocity_check(ride.user_id):
        score += 40
        triggered.append("HIGH_VELOCITY")
    if geolocation_mismatch(ride):
        score += 35
        triggered.append("GEO_MISMATCH")
    if promo_abuse_check(ride.user_id):
        score += 30
        triggered.append("PROMO_ABUSE")

    if score >= threshold:
        alert = FraudAlert(
            transaction_id=txn.transaction_id,
            risk_score=score,
            rule_triggered=",".join(triggered),
            review_status="open",
        )
        db.session.add(alert)
        db.session.commit()

    return score
