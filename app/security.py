"""
Role-based access control (Section 3.14). Every protected endpoint
declares which roles ('rider', 'driver', 'admin') may call it; a
mismatch returns 403 Forbidden, matching the RBAC test cases in
Section 3.16.4 / 4.7 ("Rider attempts to access /api/admin/fraud-alerts").
"""
from functools import wraps

from flask import jsonify
from flask_jwt_extended import verify_jwt_in_request, get_jwt, get_jwt_identity


def roles_required(*allowed_roles):
    def decorator(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            verify_jwt_in_request()
            claims = get_jwt()
            role = claims.get("role")
            if role not in allowed_roles:
                return jsonify({"detail": "Forbidden: insufficient role"}), 403
            return fn(*args, **kwargs)
        return wrapper
    return decorator


def current_identity():
    """Returns (user_id, role) for the caller of the current request."""
    claims = get_jwt()
    return get_jwt_identity(), claims.get("role")
