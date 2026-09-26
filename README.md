# RHPTPS — Ride-Hailing Payment Transaction Processing System

A working implementation of the system designed in Chapters One–Four of
the accompanying project report: a JWT-authenticated, role-based REST
API and web front end that computes fares, captures payments
idempotently against a simulated sandbox gateway, screens every
transaction with rules-based fraud detection, and gives administrators
a fraud-review and payout dashboard.

This directly implements Section 3.9 (three-tier / microservice
architecture), Section 3.11 (database schema), Section 3.14 (security
mechanisms), Section 4.3 (module-by-module implementation), and the
API table in Section 4.5. Where the project report describes something
at the architecture level (e.g. Django *and* Flask as separate
microservices behind Docker), this codebase realises it as a single,
modularly-organised Flask application — the same modules, endpoints,
schema, and idempotency/locking behaviour the report specifies, packaged
in a form one person can actually run and grade end to end. Swapping in
real separate microservices later is a deployment change, not a
redesign, since each module (`app/auth`, `app/payments`, `app/fraud`,
...) is already an independent blueprint with its own routes.

## Interface

The frontend is a hand-built single-page app (no React/Vue) — a hash
router (`static/js/app.js`) renders each screen into one shell
(`templates/index.html`), with a small custom design system
(`static/css/`) instead of a generic component kit. It's mobile-first
(bottom tab bar on phones, top bar on desktop) since riders and
drivers are expected to use this from a phone.

Interactive moments worth trying:
- **Ride screen**: submitting a trip reveals the fare as a large
  counting-up number, then "Pay now" walks a three-step progress
  indicator (Requested → Authorising → Captured) instead of a spinner.
- **Admin dashboard**: clearing or confirming a fraud alert updates
  the list immediately and confirms with a toast, no page reload.
- **Register screen**: a driver's ID is shown with a one-tap copy
  button right after signup — the ID a rider needs to book them.

Chart.js is vendored locally (`static/js/vendor/`) rather than loaded
from a CDN, so the admin dashboard's chart works offline too. Google
Fonts (Space Grotesk / IBM Plex) are the only external request the UI
makes; everything else is self-contained.

## Quick start (local, zero setup — SQLite)

```bash
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt

python seed.py        # creates a demo rider, driver and admin account
python run.py          # starts the dev server on http://localhost:5000
```

`requirements.txt` deliberately excludes `psycopg2-binary` (the
PostgreSQL driver) — it's not needed for the SQLite default, and on
some Windows/Python setups it fails to build from source unless the
Microsoft C++ Build Tools are installed. Only install it if you're
pointing `DATABASE_URL` at a real PostgreSQL server outside Docker:
`pip install -r requirements-postgres.txt`. The Docker image below
installs it automatically, since prebuilt wheels are always available
in the Linux container.

Open `http://localhost:5000` and log in as `rider@demo.com` /
`password123` (or `driver@demo.com`, `admin@demo.com` — same
password). The driver account's `driver_id` is printed by `seed.py`;
paste it into the "Driver ID" field on the ride screen.

## Quick start (Docker, PostgreSQL — matches the Section 4.2 environment table)

```bash
docker compose up --build
```

This builds the app image, brings up a PostgreSQL 15 container, creates
the tables, and serves the app on `http://localhost:5000` via
Gunicorn. Run `docker compose exec web python seed.py` once the stack
is up if you want the demo accounts.

## Running the tests

```bash
pip install -r requirements.txt
pytest -v
```

The suite (`tests/`) exercises the same scenarios as the test tables
in Sections 3.16 and 4.7: idempotent capture and retry-without-duplicate,
RBAC rejection of a rider hitting an admin endpoint, the HIGH_VELOCITY
and GEO_MISMATCH fraud rules (individually and combined past the
risk threshold), and the fare-computation formula.

**Note on a discrepancy with the report:** Section 4.7's test table
states the fare for a 7.4 km / 18-minute trip as ₦1,196.00. Applying
the report's own formula (`200 + 7.4×90 + 18×15`) gives **₦1,136.00** —
the ₦1,196.00 figure in the document is an arithmetic error, not a bug
in this implementation. Worth correcting in the write-up.

## Project layout

```
app/
  config.py          Env-driven config (SQLite default, Postgres via DATABASE_URL)
  extensions.py       Shared db / jwt instances
  models.py            SQLAlchemy models = the Section 3.11 schema
  fare.py               Fare computation (Section 4.3.2)
  gateway.py           Simulated sandbox payment gateway (Section 3.15)
  security.py          RBAC decorator (Section 3.14)
  auth/                 POST /api/auth/register, /api/auth/login
  rides/                 POST /api/rides, GET /api/rides/<id>/fare
  payments/            POST /api/payments/<ride_id>/capture,
                        GET /api/payments/<id>/status, GET /api/transactions
  fraud/                  Fraud-detection rules (Section 4.3.4)
  receipts/            GET /api/receipts/<transaction_id>
  admin/                 GET/PATCH /api/admin/fraud-alerts, GET /api/admin/payouts
  frontend/              Serves the SPA shell for every route (Section 4.6)
templates/, static/    Single-page app: hash router + custom design system, no framework
tests/                  pytest suite mirroring Sections 3.16 / 4.7
seed.py                  Demo data
run.py                   Dev server entry point
Dockerfile, docker-compose.yml   Containerised deployment (Postgres)
```

## API summary (Section 4.5)

| Method | Endpoint | Access |
|---|---|---|
| POST | /api/auth/register | Public |
| POST | /api/auth/login | Public |
| POST | /api/rides | Rider |
| GET | /api/rides/{id}/fare | Rider, Driver |
| POST | /api/payments/{ride_id}/capture | Rider |
| GET | /api/payments/{id}/status | Rider, Driver |
| GET | /api/transactions | Rider, Driver, Admin |
| GET | /api/receipts/{transaction_id} | Rider |
| GET | /api/admin/fraud-alerts | Admin |
| PATCH | /api/admin/fraud-alerts/{id} | Admin |
| GET | /api/admin/payouts | Admin |

Every protected endpoint requires `Authorization: Bearer <access_token>`
from `/api/auth/login`.

## Known scope limitations (honest, matching Section 4.9 / 1.6 of the report)

- The payment gateway is simulated (`app/gateway.py`), not a real
  Paystack/Flutterwave sandbox integration — swapping in a real SDK
  client is a contained change to that one module.
- `SELECT ... FOR UPDATE` row locking only provides real concurrency
  protection under PostgreSQL; SQLite (the zero-setup default) does not
  enforce it the same way. Use `docker compose up` to exercise the
  actual isolation guarantee described in Section 4.3.3.
- Promo-code abuse detection (`promo_abuse_check`) is stubbed to always
  return `False` — the report scopes a full `PromoRedemptions` table
  out of this project; the hook is in place for it.
- Driver payouts are reported (`GET /api/admin/payouts`) but payout
  *settlement* (moving money out) is not implemented, matching the
  report's scope.
