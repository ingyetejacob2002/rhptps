"""
Realises the database schema designed in Section 3.11 (Database Design)
and the ERD in Section 3.10.5: User, Driver, Ride, Payment, Transaction,
Fraud_Alert, Admin — with the same relationships (User 1—N Ride,
Driver 1—N Ride, Ride 1—1 Payment, Payment 1—N Transaction,
Transaction 1—0/1 Fraud_Alert).

UUIDs are stored as CHAR(36) strings so the schema runs unmodified on
both SQLite (local dev) and PostgreSQL (production, per Chapter 4).
Foreign keys and CHECK constraints are enforced at the database level,
not just in application code, per Section 4.4.
"""
import uuid
from datetime import datetime, timezone

from werkzeug.security import generate_password_hash, check_password_hash

from app.extensions import db


def gen_uuid() -> str:
    return str(uuid.uuid4())


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class User(db.Model):
    """Rider account (Users table, Section 3.11)."""
    __tablename__ = "users"

    user_id = db.Column(db.String(36), primary_key=True, default=gen_uuid)
    full_name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(100), unique=True, nullable=False, index=True)
    phone_number = db.Column(db.String(20), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    default_payment_method = db.Column(db.String(20), default="card")
    created_at = db.Column(db.DateTime, default=utcnow)

    rides = db.relationship("Ride", back_populates="rider", foreign_keys="Ride.user_id")

    role = "rider"

    def set_password(self, raw_password: str) -> None:
        self.password_hash = generate_password_hash(raw_password)

    def check_password(self, raw_password: str) -> bool:
        return check_password_hash(self.password_hash, raw_password)


class Driver(db.Model):
    """Driver account (Drivers table, Section 3.11)."""
    __tablename__ = "drivers"

    driver_id = db.Column(db.String(36), primary_key=True, default=gen_uuid)
    full_name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(100), unique=True, nullable=False, index=True)
    phone_number = db.Column(db.String(20), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    bank_account_number = db.Column(db.String(20))
    vehicle_reg_number = db.Column(db.String(20))
    rating = db.Column(db.Numeric(3, 2), default=5.00)
    created_at = db.Column(db.DateTime, default=utcnow)

    rides = db.relationship("Ride", back_populates="driver", foreign_keys="Ride.driver_id")

    role = "driver"

    def set_password(self, raw_password: str) -> None:
        self.password_hash = generate_password_hash(raw_password)

    def check_password(self, raw_password: str) -> bool:
        return check_password_hash(self.password_hash, raw_password)


class Admin(db.Model):
    """Platform administrator account (Admins table, Section 3.11)."""
    __tablename__ = "admins"

    admin_id = db.Column(db.String(36), primary_key=True, default=gen_uuid)
    full_name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(100), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    # support | fraud-review | super-admin — RBAC tier, Section 3.14
    role_level = db.Column(db.String(20), nullable=False, default="support")
    created_at = db.Column(db.DateTime, default=utcnow)

    role = "admin"

    def set_password(self, raw_password: str) -> None:
        self.password_hash = generate_password_hash(raw_password)

    def check_password(self, raw_password: str) -> bool:
        return check_password_hash(self.password_hash, raw_password)


class Ride(db.Model):
    """Trip record (Rides table, Section 3.11)."""
    __tablename__ = "rides"

    ride_id = db.Column(db.String(36), primary_key=True, default=gen_uuid)
    user_id = db.Column(db.String(36), db.ForeignKey("users.user_id"), nullable=False, index=True)
    driver_id = db.Column(db.String(36), db.ForeignKey("drivers.driver_id"), nullable=False)
    pickup_location = db.Column(db.String(255))
    dropoff_location = db.Column(db.String(255))
    distance_km = db.Column(db.Numeric(6, 2), nullable=False)
    duration_minutes = db.Column(db.Integer, nullable=False)
    ride_status = db.Column(
        db.String(20), nullable=False, default="requested"
    )  # requested | ongoing | completed | cancelled
    completed_at = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, default=utcnow)

    rider = db.relationship("User", back_populates="rides", foreign_keys=[user_id])
    driver = db.relationship("Driver", back_populates="rides", foreign_keys=[driver_id])
    payment = db.relationship("Payment", back_populates="ride", uselist=False)

    __table_args__ = (
        db.CheckConstraint(
            "ride_status IN ('requested','ongoing','completed','cancelled')",
            name="ck_ride_status",
        ),
    )


class Payment(db.Model):
    """Fare / payment-method record for a ride (Payments table, Section 3.11)."""
    __tablename__ = "payments"

    payment_id = db.Column(db.String(36), primary_key=True, default=gen_uuid)
    ride_id = db.Column(db.String(36), db.ForeignKey("rides.ride_id"), nullable=False, unique=True)
    fare_amount = db.Column(db.Numeric(10, 2), nullable=False)
    payment_method = db.Column(db.String(20), nullable=False)  # card | transfer | wallet
    payment_status = db.Column(
        db.String(20), nullable=False, default="pending"
    )  # pending | authorised | captured | failed | refunded
    gateway_reference = db.Column(db.String(100))
    created_at = db.Column(db.DateTime, default=utcnow)

    ride = db.relationship("Ride", back_populates="payment")
    transactions = db.relationship(
        "Transaction", back_populates="payment", order_by="Transaction.created_at"
    )

    __table_args__ = (
        db.CheckConstraint(
            "payment_status IN ('pending','authorised','captured','failed','refunded')",
            name="ck_payment_status",
        ),
        db.CheckConstraint("fare_amount > 0", name="ck_fare_positive"),
    )


class Transaction(db.Model):
    """
    Immutable, append-only record of a single capture/refund/payout attempt
    (Transactions table, Section 3.11). Never updated in place — see
    Section 3.14 "Audit trails" and Section 4.4.
    """
    __tablename__ = "transactions"

    transaction_id = db.Column(db.String(36), primary_key=True, default=gen_uuid)
    payment_id = db.Column(db.String(36), db.ForeignKey("payments.payment_id"), nullable=False, index=True)
    transaction_type = db.Column(db.String(20), nullable=False)  # authorisation|capture|refund|payout
    amount = db.Column(db.Numeric(10, 2), nullable=False)
    status = db.Column(db.String(20), nullable=False, default="pending", index=True)  # success|failed|pending
    idempotency_key = db.Column(db.String(64), nullable=False, unique=True)
    created_at = db.Column(db.DateTime, default=utcnow)

    payment = db.relationship("Payment", back_populates="transactions")
    fraud_alert = db.relationship("FraudAlert", back_populates="transaction", uselist=False)

    __table_args__ = (
        db.CheckConstraint("amount > 0", name="ck_txn_amount_positive"),
        db.CheckConstraint(
            "status IN ('pending','success','failed','refunded')", name="ck_txn_status"
        ),
    )


class FraudAlert(db.Model):
    """Fraud_Alerts table, Section 3.11."""
    __tablename__ = "fraud_alerts"

    alert_id = db.Column(db.String(36), primary_key=True, default=gen_uuid)
    transaction_id = db.Column(
        db.String(36), db.ForeignKey("transactions.transaction_id"), nullable=False, unique=True
    )
    risk_score = db.Column(db.Numeric(5, 2), nullable=False)
    rule_triggered = db.Column(db.String(100), nullable=False)
    review_status = db.Column(
        db.String(20), nullable=False, default="open"
    )  # open | under_review | cleared | confirmed_fraud
    reviewed_by = db.Column(db.String(36), db.ForeignKey("admins.admin_id"), nullable=True)
    created_at = db.Column(db.DateTime, default=utcnow)

    transaction = db.relationship("Transaction", back_populates="fraud_alert")

    __table_args__ = (
        db.CheckConstraint(
            "review_status IN ('open','under_review','cleared','confirmed_fraud')",
            name="ck_alert_review_status",
        ),
    )
