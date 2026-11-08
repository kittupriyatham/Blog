"""API v1 registration."""

from core.api.v1.posts import api_v1 as posts_bp
from core.api.v1.author import author_bp


def register_api_v1(app, csrf=None):
    """Register all v1 API blueprints under /api/v1 prefix."""
    app.register_blueprint(posts_bp, url_prefix="/api/v1")
    app.register_blueprint(author_bp, url_prefix="/api/v1")

    # Mobile API clients send JSON payloads without browser CSRF cookies
    if csrf is not None:
        try:
            csrf.exempt(posts_bp)
            csrf.exempt(author_bp)
        except Exception as e:
            print(f"[api_v1] Note: csrf exemption skipped: {e}")


__all__ = ["register_api_v1", "posts_bp", "author_bp"]
