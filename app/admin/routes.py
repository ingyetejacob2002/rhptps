"""
Admin monitoring module (Section 4.3.6). Read access to transaction
volume / open fraud alerts and write access to the fraud-review
workflow, gated entirely by role='admin' (RBAC, Section 3.14). The
role_level tier (support / fraud-review / super-admin) is modelled on
the Admin account but this project's endpoints only enforce the
coarse-grained admin/non-admin boundary the test cases in Section 3.16
exercise; role_level is available for a finer-grained policy to be
layered on later without a schema change.

Endpoints (Section 4.5):
    GET   /api/admin/fraud-alerts       - Admin
    PATCH /api/admin/fraud-alerts/<id>  - Admin
    GET   /api/admin/payouts            - Admin
"""
from flask import Blueprint, jsonify, request

from app.extensions import db
from app.models import FraudAlert, Transaction, Payment, Ride, Driver
from app.security import roles_required, current_identity

admin_bp = Blueprint("admin", __name__, url_prefix="/api/admin")

VALID_REVIEW_STATUSES = {"open", "under_review", "cleared", "confirmed_fraud"}


@admin_bp.get("/fraud-alerts")
@roles_required("admin")
def list_fraud_alerts():
    status_filter = request.args.get("status", "open")
    query = FraudAlert.query
    if status_filter != "all":
        query = query.filter_by(review_status=status_filter)
    alerts = query.order_by(FraudAlert.created_at.desc()).all()
    return jsonify([{
        "alert_id": a.alert_id,
        "transaction_id": a.transaction_id,
        "risk_score": str(a.risk_score),
        "rule_triggered": a.rule_triggered,
        "review_status": a.review_status,
        "created_at": a.created_at.isoformat() if a.created_at else None,
    } for a in alerts]), 200


@admin_bp.patch("/fraud-alerts/<alert_id>")
@roles_required("admin")
def update_fraud_alert(alert_id):
    alert = FraudAlert.query.get_or_404(alert_id)
    data = request.get_json(silent=True) or {}
    new_status = data.get("review_status")

    if new_status not in VALID_REVIEW_STATUSES:
        return jsonify({
            "detail": "review_status must be one of " + ", ".join(sorted(VALID_REVIEW_STATUSES))
        }), 400

    admin_id, _role = current_identity()
    alert.review_status = new_status
    alert.reviewed_by = admin_id
    db.session.commit()

    return jsonify({
        "alert_id": alert.alert_id,
        "review_status": alert.review_status,
        "reviewed_by": alert.reviewed_by,
    }), 200


@admin_bp.get("/payouts")
@roles_required("admin")
def list_payouts():
    """
    Driver payout view: aggregates captured payments per driver into
    pending vs settled buckets. 'settled' means a transaction of type
    'payout' already exists for that payment; this project does not
    implement the settlement-initiation side of that transition, only
    the reporting view described in Section 4.5.
    """
    rows = (
        db.session.query(Driver, Ride, Payment)
        .join(Ride, Ride.driver_id == Driver.driver_id)
        .join(Payment, Payment.ride_id == Ride.ride_id)
        .filter(Payment.payment_status == "captured")
        .all()
    )

    payouts = {}
    for driver, ride, payment in rows:
        settled = Transaction.query.filter_by(
            payment_id=payment.payment_id, transaction_type="payout", status="success"
        ).first() is not None

        bucket = payouts.setdefault(driver.driver_id, {
            "driver_id": driver.driver_id,
            "driver_name": driver.full_name,
            "pending_amount": 0.0,
            "settled_amount": 0.0,
        })
        amount = float(payment.fare_amount)
        if settled:
            bucket["settled_amount"] += amount
        else:
            bucket["pending_amount"] += amount

    return jsonify(list(payouts.values())), 200
