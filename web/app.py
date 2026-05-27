"""CxKitty Web UI — Flask desktop application."""

import secrets
import sys
import threading
import webbrowser
import traceback
import logging
from pathlib import Path

from flask import Flask, redirect, render_template, request, session, url_for

# Ensure project root is on sys.path for imports
_PROJECT_ROOT = Path(__file__).parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from cxapi.api import ChaoXingAPI
from utils import ck2dict, sessions_load


def create_app() -> Flask:
    app = Flask(__name__)
    app.secret_key = secrets.token_hex(32)

    from web.routes.auth import auth_bp
    from web.routes.courses import courses_bp
    from web.routes.export import export_bp
    from web.routes.exam import exam_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(courses_bp)
    app.register_blueprint(export_bp)
    app.register_blueprint(exam_bp)

    @app.route("/")
    def index():
        if session.get("phone"):
            return redirect(url_for("courses.list_courses"))
        return redirect(url_for("auth.login_page"))

    @app.errorhandler(404)
    def not_found(e):
        return f"<pre>404: {request.url}\n\nRegistered routes:\n" + \
               "\n".join(sorted(r.rule for r in app.url_map.iter_rules() if not r.rule.startswith('/static'))) + \
               "</pre>", 404

    @app.errorhandler(500)
    def server_error(e):
        orig = getattr(e, "original_exception", e)
        tb = "".join(traceback.format_exception(type(orig), orig, orig.__traceback__)) if orig else str(e)
        return render_template("error.html", message=f"500: {orig}"), 500

    return app


def _load_api_for_phone(phone: str) -> ChaoXingAPI | None:
    """Create ChaoXingAPI and load saved cookies for a given phone number."""
    api = ChaoXingAPI()
    saved = sessions_load()
    for s in saved:
        if s.phone == phone:
            api.ck_load(ck2dict(s.ck))
            if api.accinfo():
                return api
            break
    return None


def get_api() -> ChaoXingAPI | None:
    phone = session.get("phone")
    if not phone:
        return None
    api = _load_api_for_phone(phone)
    if not api:
        session.clear()
    return api


def main():
    app = create_app()

    def open_browser():
        webbrowser.open("http://127.0.0.1:5000")

    threading.Timer(0.8, open_browser).start()
    logging.getLogger("werkzeug").setLevel(logging.WARNING)
    app.run(host="127.0.0.1", port=5000, debug=True, use_reloader=False)


if __name__ == "__main__":
    main()
