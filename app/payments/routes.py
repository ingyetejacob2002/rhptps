"""
Payment-processing module (Section 4.3.3) — the core of the RHPTPS.

Implements the exact idempotency + ACID discipline described in the
project: a client-supplied idempotency_key is checked before any new
capture attempt (duplicate-transaction safeguard, Section 3.8.1); the
Payment row is locked with SELECT ... FOR UPDATE for the duration of
the capture so two concurrent requests for the same ride cannot both
charge the gateway (Isolation); the transaction insert and payment
status update commit together or not at all (Atomicity); and a UNIQUE
constraint on idempotency_key is the database-level backstop if the
application-level check is ever raced (Consistency).

Note: SQLite (the local zero-setup default) does not honour FOR UPDATE
row locks the way PostgreSQL does — see README.md. Run against
PostgreSQL (docker-compose.yml provides one) to exercise the real
concurrency guarantee the project claims.

Endpoints (Section 4.5):
    POST /api/payments/<ride_id>/capture  - Rider
    GET  /api/payments/<id>/status        - Rider, Driver
    GET  /api/transactions                - Rider, Driver, Admin
"""
from flask import Blueprint, jsonify, request
from sqlalchemy.exc import IntegrityError

from app.extensions import db
from app.models import Payment, Transaction, Ride
from app import gateway
from app.fraud.rules import evaluate as evaluate_fraud
from app.security import roles_required, current_identity

payments_bp = Blueprint("payments", __name__, url_prefix="/api/payments")


def process_payment(ride_id: str, idempotency_key: str):
    """
    Returns (transaction, http_status). Mirrors payments/services.py in
    Section 4.3.3 exactly, adapted to Flask-SQLAlchemy's session API.
    """
    # Short-circuit on a retried request before touching the row lock at all.
    existing = Transaction.query.filter_by(idempotency_key=idempotency_key).first()
    if existing:
        return existing, 200

    payment = Payment.query.filter_by(ride_id=ride_id).first()
    if payment is None:
        return None, 404

    try:
        # -- ISOLATION: no second request can act on this Payment row
        # until this transaction commits or rolls back.
        locked_payment = (
            db.session.query(Payment)
            .filter_by(payment_id=payment.payment_id)
            .with_for_update()
            .first()
        )

        if locked_payment.payment_status == "captured":
            # Another request already captured this ride while we waited
            # for the lock; nothing further to do.
            return locked_payment.transactions[-1], 200

        gateway_response = gateway.charge(
            amount=float(locked_payment.fare_amount),
            method=locked_payment.payment_method,
            reference=idempotency_key,
        )

        transaction = Transaction(
            payment_id=locked_payment.payment_id,
            transaction_type="capture",
            amount=locked_payment.fare_amount,
            status="success" if gateway_response.ok else "failed",
            idempotency_key=idempotency_key,
        )
        db.session.add(transaction)
        locked_payment.payment_status = "captured" if gateway_response.ok else "failed"
        locked_payment.gateway_reference = gateway_response.reference

        # -- ATOMICITY / DURABILITY: both writes commit together, or
        # neither does; once commit() returns, PostgreSQL's WAL has
        # fsynced the change to disk.
        db.session.commit()

    except IntegrityError:
        # A concurrent request with the SAME idempotency key won the
        # unique-constraint race; roll back our attempt and return theirs.
        db.session.rollback()
        winner = Transaction.query.filter_by(idempotency_key=idempotency_key).first()
        return winner, 200

    if transaction.status == "success":
        evaluate_fraud(transaction.transaction_id)

    return transaction, 201 if transaction.status == "success" else 402


@payments_bp.post("/<ride_id>/capture")
@roles_required("rider")
def capture(ride_id):
    data = request.get_json(silent=True) or {}
    idempotency_key = data.get("idempotency_key")
    if not idempotency_key:
        return jsonify({"detail": "idempotency_key is required"}), 400

    ride = Ride.query.get_or_404(ride_id)
    user_id, _role = current_identity()
    if ride.user_id != user_id:
        return jsonify({"detail": "Forbidden: not your ride"}), 403

    transaction, status_code = process_payment(ride_id, idempotency_key)
    if transaction is None:
        return jsonify({"detail": "No payment record for this ride"}), status_code

    return jsonify({
        "transaction_id": transaction.transaction_id,
        "payment_id": transaction.payment_id,
        "status": transaction.status,
        "amount": str(transaction.amount),
        "idempotency_key": transaction.idempotency_key,
    }), status_code


@payments_bp.get("/<payment_id>/status")
@roles_required("rider", "driver")
def status(payment_id):
    payment = Payment.query.get_or_404(payment_id)
    return jsonify({
        "payment_id": payment.payment_id,
        "ride_id": payment.ride_id,
        "payment_status": payment.payment_status,
        "fare_amount": str(payment.fare_amount),
        "gateway_reference": payment.gateway_reference,
    }), 200


# Separate blueprint: GET /api/transactions lives outside the /api/payments
# prefix per the API table in Section 4.5.
transactions_bp = Blueprint("transactions", __name__, url_prefix="/api/transactions")


@transactions_bp.get("")
@roles_required("rider", "driver", "admin")
def list_transactions():
    user_id, role = current_identity()
    query = Transaction.query.join(Payment).join(Ride)

    if role == "rider":
        query = query.filter(Ride.user_id == user_id)
    elif role == "driver":
        query = query.filter(Ride.driver_id == user_id)
    # admin: unfiltered, per Section 3.8.1 "consolidated view of transaction volume"

    status_filter = request.args.get("status")
    if status_filter:
        query = query.filter(Transaction.status == status_filter)

    results = query.order_by(Transaction.created_at.desc()).limit(200).all()
    return jsonify([{
        "transaction_id": t.transaction_id,
        "payment_id": t.payment_id,
        "transaction_type": t.transaction_type,
        "amount": str(t.amount),
        "status": t.status,
        "created_at": t.created_at.isoformat() if t.created_at else None,
    } for t in results]), 200
