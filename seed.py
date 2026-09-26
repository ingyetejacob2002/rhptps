"""
Seeds the database with one rider, one driver and one admin account so
the UI and API can be explored immediately without registering first.

Usage:
    python seed.py
"""
from app import create_app
from app.extensions import db
from app.models import User, Driver, Admin

app = create_app()

with app.app_context():
    db.create_all()

    if not User.query.filter_by(email="rider@demo.com").first():
        rider = User(
            full_name="Ada Rider",
            email="rider@demo.com",
            phone_number="08011111111",
            default_payment_method="card",
        )
        rider.set_password("password123")
        db.session.add(rider)

    if not Driver.query.filter_by(email="driver@demo.com").first():
        driver = Driver(
            full_name="Musa Driver",
            email="driver@demo.com",
            phone_number="08022222222",
            bank_account_number="0123456789",
            vehicle_reg_number="BEN123XY",
        )
        driver.set_password("password123")
        db.session.add(driver)

    if not Admin.query.filter_by(email="admin@demo.com").first():
        admin = Admin(
            full_name="Admin User",
            email="admin@demo.com",
            role_level="super-admin",
        )
        admin.set_password("password123")
        db.session.add(admin)

    db.session.commit()

    print("Seeded demo accounts (password for all: password123):")
    print("  Rider: rider@demo.com")
    print("  Driver: driver@demo.com  (driver_id: {})".format(
        Driver.query.filter_by(email="driver@demo.com").first().driver_id
    ))
    print("  Admin: admin@demo.com")
