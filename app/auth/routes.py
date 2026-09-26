"""
Authentication module (Section 4.3.1). Issues short-lived JWT access
tokens carrying an embedded 'role' claim (rider | driver | admin), which
security.roles_required() checks on every protected request.

Endpoints (Section 4.5):
    POST /api/auth/register  - Public
    POST /api/auth/login     - Public
"""
import re

from flask import Blueprint, jsonify, request
from flask_jwt_extended import create_access_token, create_refresh_token

from app.extensions import db
from app.models import User, Driver, Admin

auth_bp = Blueprint("auth", __name__, url_prefix="/api/auth")

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
# Nigerian numbering convention: +234 or 0, followed by 10 digits (Section 3.12)
PHONE_RE = re.compile(r"^(?:\+234|0)\d{10}$")

ROLE_MODELS = {"rider": User, "driver": Driver}


def _validate_registration(data):
    errors = []
    if data.get("role") not in ROLE_MODELS:
        errors.append("role must be 'rider' or 'driver'")
    if not data.get("full_name"):
        errors.append("full_name is required")
    if not data.get("email") or not EMAIL_RE.match(data.get("email", "")):
        errors.append("a valid email is required")
    if not data.get("phone_number") or not PHONE_RE.match(data.get("phone_number", "")):
        errors.append("phone_number must be a valid Nigerian number (e.g. 08012345678)")
    password = data.get("password", "")
    if len(password) < 8:
        errors.append("password must be at least 8 characters")
    return errors


@auth_bp.post("/register")
def register():
    data = request.get_json(silent=True) or {}
    errors = _validate_registration(data)
    if errors:
        return jsonify({"detail": "Validation failed", "errors": errors}), 400

    role = data["role"]
    model = ROLE_MODELS[role]

    if model.query.filter(
        (model.email == data["email"]) | (model.phone_number == data["phone_number"])
    ).first():
        return jsonify({"detail": "An account with this email or phone number already exists"}), 409

    if role == "rider":
        account = User(
            full_name=data["full_name"],
            email=data["email"],
            phone_number=data["phone_number"],
            default_payment_method=data.get("default_payment_method", "card"),
        )
    else:
        account = Driver(
            full_name=data["full_name"],
            email=data["email"],
            phone_number=data["phone_number"],
            bank_account_number=data.get("bank_account_number"),
            vehicle_reg_number=data.get("vehicle_reg_number"),
        )
    account.set_password(data["password"])
    db.session.add(account)
    db.session.commit()

    return jsonify({
        "detail": "Account created",
        "id": account.user_id if role == "rider" else account.driver_id,
        "role": role,
    }), 201


@auth_bp.post("/login")
def login():
    data = request.get_json(silent=True) or {}
    email = data.get("email")
    password = data.get("password")
    if not email or not password:
        return jsonify({"detail": "email and password are required"}), 400

    login_models = {**ROLE_MODELS, "admin": Admin}
    account = None
    role = None
    for candidate_role, model in login_models.items():
        found = model.query.filter_by(email=email).first()
        if found:
            account, role = found, candidate_role
            break

    if account is None or not account.check_password(password):
        return jsonify({"detail": "Invalid credentials"}), 401

    account_id = getattr(account, "user_id", None) or getattr(account, "driver_id", None) or getattr(account, "admin_id", None)

    additional_claims = {"role": role}
    access_token = create_access_token(identity=account_id, additional_claims=additional_claims)
    refresh_token = create_refresh_token(identity=account_id, additional_claims=additional_claims)

    return jsonify({
        "access": access_token,
        "refresh": refresh_token,
        "role": role,
        "id": account_id,
        "full_name": account.full_name,
    }), 200
