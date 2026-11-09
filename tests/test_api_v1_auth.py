"""Tests for mobile authentication endpoints."""

from unittest.mock import patch

from app import app


def test_mobile_demo_login_creates_demo_session():
    app.config["TESTING"] = True
    with app.test_client() as client:
        response = client.post(
            "/api/v1/auth/login",
            json={"username": "demo", "password": "demo"},
        )
        assert response.status_code == 200
        assert response.get_json()["user"] == {
            "username": "Demo Publisher",
            "is_demo": True,
            "is_admin": False,
        }

        me = client.get("/api/v1/auth/me")
        assert me.status_code == 200
        assert me.get_json()["user"]["is_demo"] is True


def test_mobile_admin_login_creates_admin_session():
    app.config["TESTING"] = True
    with patch("core.api.v1.auth.ADMIN_USERNAME", "admin"), \
         patch("core.api.v1.auth.ADMIN_PASSWORD", "secret"):
        with app.test_client() as client:
            response = client.post(
                "/api/v1/auth/login",
                json={"username": "admin", "password": "secret"},
            )
            assert response.status_code == 200
            assert response.get_json()["user"]["is_admin"] is True


def test_mobile_login_rejects_invalid_credentials():
    app.config["TESTING"] = True
    with app.test_client() as client:
        response = client.post(
            "/api/v1/auth/login",
            json={"username": "admin", "password": "wrong"},
        )
        assert response.status_code == 401
