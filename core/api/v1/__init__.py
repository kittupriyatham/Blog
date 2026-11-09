"""API v1 registration."""

from core.api.v1.posts import api_v1 as posts_bp
from core.api.v1.author import author_bp
from core.api.v1.auth import auth_bp


def register_api_v1(app, csrf=None):
    """Register all v1 API blueprints under /api/v1 prefix."""
    app.register_blueprint(posts_bp, url_prefix="/api/v1")
    app.register_blueprint(author_bp, url_prefix="/api/v1")
    app.register_blueprint(auth_bp, url_prefix="/api/v1")

    # Keep existing public mutation and native authentication behavior.
    if csrf is not None:
        try:
            # Creation validates CSRF itself, with a narrow native-session path.
            from core.api.v1.posts import (
                create_post,
                upload_media_v1,
                add_post_comment,
                react_to_post,
                share_post,
            )
            for view in (create_post, upload_media_v1, add_post_comment, react_to_post, share_post):
                csrf.exempt(view)
            csrf.exempt(author_bp)
            csrf.exempt(auth_bp)
        except Exception as e:
            print(f"[api_v1] Note: csrf exemption skipped: {e}")


__all__ = ["register_api_v1", "posts_bp", "author_bp", "auth_bp"]
