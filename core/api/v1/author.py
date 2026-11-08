"""REST API endpoints for Author metadata and profile information."""

from flask import Blueprint, jsonify
from core.author import AUTHOR_INFO

author_bp = Blueprint("api_v1_author", __name__)


@author_bp.route("/author", methods=["GET"])
def get_author():
    """Retrieve public author profile, biography, domains, and social links."""
    return jsonify({
        "status": "success",
        "author": AUTHOR_INFO,
    })
