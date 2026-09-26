"""
Rides module.

Endpoints (Section 4.5):
    POST /api/rides              - Rider  - create a ride + open its Payment record
    GET  /api/rides/<id>/fare    - Rider, Driver - retrieve the computed fare
"""
from flask import Blueprint, jsonify, request

from app.extensions import db
from app.models import Ride, Payment, Driver
from app.fare import compute_fare
from app.security import roles_required, current_identity

rides_bp = Blueprint("rides", __name__, url_prefix="/api/rides")


@rides_bp.post("")
@roles_required("rider")
def create_ride():
    data = request.get_json(silent=True) or {}
    user_id, _role = current_identity()

    required = ["driver_id", "distance_km", "duration_minutes"]
    missing = [f for f in required if data.get(f) in (None, "")]
    if missing:
        return jsonify({"detail": "Validation failed", "missing": missing}), 400

    if not Driver.query.get(data["driver_id"]):
        return jsonify({"detail": "driver_id does not reference a known driver"}), 404

    ride = Ride(
        user_id=user_id,
        driver_id=data["driver_id"],
        pickup_location=data.get("pickup_location", ""),
        dropoff_location=data.get("dropoff_location", ""),
        distance_km=data["distance_km"],
        duration_minutes=data["duration_minutes"],
        ride_status="completed",
    )
    db.session.add(ride)
    db.session.flush()  # assigns ride.ride_id

    fare = compute_fare(
        distance_km=float(data["distance_km"]),
        duration_minutes=int(data["duration_minutes"]),
        surge_multiplier=float(data.get("surge_multiplier", 1.0)),
        promo_discount=float(data.get("promo_discount", 0.0)),
    )

    payment = Payment(
        ride_id=ride.ride_id,
        fare_amount=fare,
        payment_method=data.get("payment_method", "card"),
        payment_status="pending",
    )
    db.session.add(payment)
    db.session.commit()

    return jsonify({
        "ride_id": ride.ride_id,
        "payment_id": payment.payment_id,
        "fare_amount": str(payment.fare_amount),
        "ride_status": ride.ride_status,
    }), 201


@rides_bp.get("/<ride_id>/fare")
@roles_required("rider", "driver")
def get_fare(ride_id):
    ride = Ride.query.get_or_404(ride_id)
    if not ride.payment:
        return jsonify({"detail": "No payment record for this ride yet"}), 404
    return jsonify({
        "ride_id": ride.ride_id,
        "distance_km": str(ride.distance_km),
        "duration_minutes": ride.duration_minutes,
        "fare_amount": str(ride.payment.fare_amount),
    }), 200
