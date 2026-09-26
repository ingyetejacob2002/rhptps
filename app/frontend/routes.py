"""
Presentation layer (Section 4.6). A single-page shell (index.html) is
served for the app root and every client-side route so deep links and
page refreshes work; static/js/app.js's hash router then renders the
right screen (login, ride & payment, receipt, driver profile, admin
dashboard) into it.
"""
from flask import Blueprint, render_template

frontend_bp = Blueprint("frontend", __name__)

# Path-based entry points that should still serve the shell on a hard
# refresh or direct visit. The hash portion (e.g. #/ride) needs no
# server route at all -- only these do, so a refresh on /admin, say,
# doesn't 404.
_SPA_PATHS = ["/", "/ride", "/receipt", "/driver", "/admin"]


def _shell():
    return render_template("index.html")


for _path in _SPA_PATHS:
    _endpoint = "spa_root" if _path == "/" else f"spa_{_path.strip('/')}"
    frontend_bp.add_url_rule(_path, endpoint=_endpoint, view_func=_shell)
