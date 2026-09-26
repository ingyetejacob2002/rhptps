"""
Transaction logging / receipt module (Section 4.3.5). A structured
digital receipt is generated the moment a capture succeeds; this module
exposes it for retrieval as JSON (Section 4.5: GET /api/receipts/<id>).
"""
from uuid import uuid4

from flask import Blueprint, jsonify

from app.models import Transaction
from app.security import roles_required, current_identity

receipts_bp = Blueprint("receipts", __name__, url_prefix="/api/receipts")


def generate_receipt(transaction: Transaction) -> dict:
    return {
        "receipt_id": str(uuid4()),
        "ride_id": transaction.payment.ride_id,
        "fare_amount": str(transaction.amount),
        "payment_method": transaction.payment.payment_method,
        "status": transaction.status,
        "timestamp": transaction.created_at.isoformat() if transaction.created_at else None,
        "reference": transaction.idempotency_key,
    }


@receipts_bp.get("/<transaction_id>")
@roles_required("rider")
def get_receipt(transaction_id):
    transaction = Transaction.query.get_or_404(transaction_id)
    user_id, _role = current_identity()
    if transaction.payment.ride.user_id != user_id:
        return jsonify({"detail": "Forbidden: not your transaction"}), 403
    if transaction.status != "success":
        return jsonify({"detail": "No receipt available: payment was not captured"}), 404
    return jsonify(generate_receipt(transaction)), 200
