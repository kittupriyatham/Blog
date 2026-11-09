"""Authentication endpoints for mobile clients."""

import hmac

from flask import Blueprint, jsonify, request, session

from core.config import ADMIN_PASSWORD, ADMIN_USERNAME

auth_bp = Blueprint("api_v1_auth", __name__)
MOBILE_CLIENT_HEADER = "X-Mobile-Client"
MOBILE_CLIENT_VALUE = "blog-android"


def _credentials(data):
    username = str(data.get("username") or "").strip()
    password = str(data.get("password") or "").strip()
    return username, password


def _mobile_request():
    return request.headers.get(MOBILE_CLIENT_HEADER) == MOBILE_CLIENT_VALUE


def _set_session(username, is_demo):
    session.clear()
    session["logged_in"] = True
    session["is_demo"] = is_demo
    session["username"] = username


@auth_bp.route("/auth/login", methods=["POST"])
def login():
    """Create the same session used by the web admin for the native mobile client."""
    if not _mobile_request() or not request.is_json:
        return jsonify({"status": "error", "message": "Mobile JSON client required."}), 400
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return jsonify({"status": "error", "message": "Credentials must be a JSON object."}), 400
    username, password = _credentials(data)

    is_demo = username.lower() == "demo" and password.lower() == "demo"
    is_admin = bool(ADMIN_USERNAME and ADMIN_PASSWORD) and (
        hmac.compare_digest(username.encode("utf-8"), ADMIN_USERNAME.encode("utf-8"))
        and hmac.compare_digest(password.encode("utf-8"), ADMIN_PASSWORD.encode("utf-8"))
    )

    if not (is_demo or is_admin):
        return jsonify({"status": "error", "message": "Invalid credentials."}), 401

    account_name = "Demo Publisher" if is_demo else ADMIN_USERNAME
    _set_session(account_name, is_demo)
    return jsonify({
        "status": "success",
        "user": {
            "username": account_name,
            "is_demo": is_demo,
            "is_admin": not is_demo,
        },
    })


@auth_bp.route("/auth/me", methods=["GET"])
def current_user():
    """Return the authenticated mobile session, if one exists."""
    if not session.get("logged_in") or "is_demo" not in session:
        return jsonify({"status": "error", "message": "Not authenticated."}), 401
    return jsonify({
        "status": "success",
        "user": {
            "username": session.get("username", ""),
            "is_demo": bool(session.get("is_demo")),
            "is_admin": not bool(session.get("is_demo")),
        },
    })


@auth_bp.route("/auth/logout", methods=["POST"])
def logout():
    if not _mobile_request():
        return jsonify({"status": "error", "message": "Mobile client required."}), 400
    session.clear()
    return jsonify({"status": "success"})
