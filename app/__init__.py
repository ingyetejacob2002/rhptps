import os

from flask import Flask

from app.config import Config
from app.extensions import db, jwt

# app/__init__.py lives inside the app/ package; templates/ and static/
# live one level up, at the project root — point Flask there explicitly
# instead of relying on its default (which looks inside app/).
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def create_app(config_object=Config):
    app = Flask(
        __name__,
        template_folder=os.path.join(PROJECT_ROOT, "templates"),
        static_folder=os.path.join(PROJECT_ROOT, "static"),
    )
    app.config.from_object(config_object)

    db.init_app(app)
    jwt.init_app(app)

    from app.auth.routes import auth_bp
    from app.rides.routes import rides_bp
    from app.payments.routes import payments_bp, transactions_bp
    from app.receipts.routes import receipts_bp
    from app.admin.routes import admin_bp
    from app.frontend.routes import frontend_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(rides_bp)
    app.register_blueprint(payments_bp)
    app.register_blueprint(transactions_bp)
    app.register_blueprint(receipts_bp)
    app.register_blueprint(admin_bp)
    app.register_blueprint(frontend_bp)

    @app.get("/api/health")
    def health():
        return {"status": "ok", "service": "RHPTPS"}, 200

    return app
