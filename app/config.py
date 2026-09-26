"""
Configuration for the RHPTPS backend.

Chapter 3 / Chapter 4 of the project specify PostgreSQL as the
production database (transactional integrity, FOR UPDATE row locking).
For a zero-setup local demo this defaults to SQLite, but every model,
constraint and query is written in standard SQLAlchemy so switching to
Postgres is just a matter of setting DATABASE_URL — see README.md.
"""
import os
from datetime import timedelta


class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY", "dev-secret-change-in-production")

    SQLALCHEMY_DATABASE_URI = os.environ.get(
        "DATABASE_URL", "sqlite:///rhptps.db"
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    JWT_SECRET_KEY = os.environ.get("JWT_SECRET_KEY", "dev-jwt-secret-change-in-production")
    JWT_ACCESS_TOKEN_EXPIRES = timedelta(minutes=15)
    JWT_REFRESH_TOKEN_EXPIRES = timedelta(days=7)

    # Fraud detection (Section 4.3.4)
    FRAUD_RISK_THRESHOLD = 70
    FRAUD_VELOCITY_WINDOW_MINUTES = 2
    FRAUD_VELOCITY_TRIP_COUNT = 2

    # Fare computation (Section 4.3.2)
    BASE_FARE = 200.00
    RATE_PER_KM = 90.00
    RATE_PER_MINUTE = 15.00

    # Simulated sandbox payment gateway (Section 3.15 / 4.2)
    GATEWAY_SIMULATED_FAILURE_RATE = float(os.environ.get("GATEWAY_SIMULATED_FAILURE_RATE", "0.0"))
    GATEWAY_LATENCY_SECONDS = float(os.environ.get("GATEWAY_LATENCY_SECONDS", "0.0"))


class TestConfig(Config):
    TESTING = True
    SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"
    JWT_ACCESS_TOKEN_EXPIRES = timedelta(minutes=15)
