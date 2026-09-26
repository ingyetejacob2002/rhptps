"""
Fare-computation module (Section 4.3.2). This is the single authoritative
source both the payment-processing module and rider/driver-facing
screens read from (Section 3.7 requirement).
"""
from flask import current_app


def compute_fare(
    distance_km: float,
    duration_minutes: int,
    surge_multiplier: float = 1.0,
    promo_discount: float = 0.0,
) -> float:
    base_fare = current_app.config["BASE_FARE"]
    rate_per_km = current_app.config["RATE_PER_KM"]
    rate_per_minute = current_app.config["RATE_PER_MINUTE"]

    raw_fare = base_fare + (distance_km * rate_per_km) + (duration_minutes * rate_per_minute)
    surged_fare = raw_fare * surge_multiplier
    final_fare = max(surged_fare - promo_discount, base_fare)
    return round(final_fare, 2)
