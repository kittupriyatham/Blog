"""Authentication endpoints for mobile clients."""

import hmac

from flask import Blueprint, jsonify, request, session

from core.config import ADMIN_PASSWORD, ADMIN_USERNAME

auth_bp = Blueprint("api_v1_auth", __name__)


def _credentials(data):
    username = str(data.get("username") or "").strip()
    password = str(data.get("password") or "").strip()
    return username, password


def _set_session(username, is_demo):
    session.clear()
    session["logged_in"] = True
    session["is_demo"] = is_demo
    session["username"] = username


@auth_bp.route("/auth/login", methods=["POST"])
def login():
    """Create the same session used by the web admin, accepting JSON or form data."""
    data = request.get_json(silent=True) or request.form
    username, password = _credentials(data)

    is_demo = username.lower() == "demo" and password.lower() == "demo"
    is_admin = bool(ADMIN_USERNAME and ADMIN_PASSWORD) and (
        hmac.compare_digest(username, ADMIN_USERNAME)
        and hmac.compare_digest(password, ADMIN_PASSWORD)
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
    if not session.get("logged_in"):
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
    session.clear()
    return jsonify({"status": "success"})
