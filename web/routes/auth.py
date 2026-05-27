"""Login/logout routes."""

import io
from flask import Blueprint, flash, jsonify, redirect, render_template, request, session, url_for
from qrcode import QRCode
from qrcode.image.svg import SvgPathImage

from cxapi.api import ChaoXingAPI
from web.app import get_api
from utils import save_session

auth_bp = Blueprint("auth", __name__)

# In-memory store for QR polling state across requests
_qr_states: dict[str, dict] = {}


@auth_bp.route("/login")
def login_page():
    if session.get("phone"):
        return redirect(url_for("courses.list_courses"))
    return render_template("login.html")


@auth_bp.route("/login/password", methods=["POST"])
def login_password():
    phone = request.form.get("phone", "").strip()
    passwd = request.form.get("password", "").strip()
    if not phone or not passwd:
        flash("手机号和密码不能为空", "error")
        return redirect(url_for("auth.login_page"))

    api = get_api() or ChaoXingAPI()
    ok, resp = api.login_passwd(phone, passwd)
    if not ok:
        flash(f"登录失败: {resp}", "error")
        return redirect(url_for("auth.login_page"))

    api.accinfo()
    save_session(api.ck_dump(), api.acc, passwd)
    session["phone"] = api.acc.phone
    session["name"] = api.acc.name
    session["puid"] = api.acc.puid
    flash(f"登录成功，欢迎 {api.acc.name}", "success")
    return redirect(url_for("courses.list_courses"))


@auth_bp.route("/login/qr")
def login_qr_page():
    """Render QR code login tab content."""
    if session.get("phone"):
        return redirect(url_for("courses.list_courses"))

    api = ChaoXingAPI()
    api.qr_get()
    qr_url = api.qr_geturl()

    # Store QR state for polling
    qr_state = {"uuid": api.qr_uuid, "enc": api.qr_enc}
    _qr_states["current"] = qr_state

    # Generate SVG QR code
    qr = QRCode(border=1)
    qr.add_data(qr_url)
    qr.make()
    img = qr.make_image(image_factory=SvgPathImage)
    buf = io.BytesIO()
    img.save(buf)
    svg = buf.getvalue().decode("utf-8")

    return render_template("login.html", qr_svg=svg, qr_tab=True)


@auth_bp.route("/login/qr/status")
def login_qr_status():
    """Poll QR code scan status. Returns JSON."""
    state = _qr_states.get("current")
    if not state:
        return jsonify({"status": False, "type": "1", "msg": "二维码已过期，请刷新"})

    api = ChaoXingAPI()
    api.qr_uuid = state["uuid"]
    api.qr_enc = state["enc"]
    result = api.login_qr()

    if result.get("status") is True:
        api.accinfo()
        save_session(api.ck_dump(), api.acc)
        session["phone"] = api.acc.phone
        session["name"] = api.acc.name
        session["puid"] = api.acc.puid
        _qr_states.pop("current", None)
        return jsonify({"status": True, "msg": "登录成功"})

    return jsonify({
        "status": False,
        "type": result.get("type", ""),
        "msg": result.get("msg", result.get("status", "等待扫描...")),
    })


@auth_bp.route("/logout")
def logout():
    session.clear()
    flash("已退出登录", "info")
    return redirect(url_for("auth.login_page"))

