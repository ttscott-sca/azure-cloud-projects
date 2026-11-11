import pytest

import app as app_module


@pytest.fixture()
def client():
    app_module.app.config.update(TESTING=True)
    return app_module.app.test_client()


def test_home_page_renders(client):
    response = client.get("/")
    assert response.status_code == 200
    assert b"Azure Cloud Project" in response.data


def test_health_endpoint(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.get_json() == {"status": "ok"}


def test_info_endpoint_has_expected_keys(client):
    data = client.get("/api/info").get_json()
    for key in ("app", "region", "version", "python", "uptime_seconds", "monitoring"):
        assert key in data


def test_info_does_not_leak_environment(client):
    body = client.get("/api/info").get_data(as_text=True).lower()
    for word in ("connection", "secret", "password", "key="):
        assert word not in body


def test_security_headers_present(client):
    headers = client.get("/").headers
    assert headers["X-Content-Type-Options"] == "nosniff"
    assert headers["X-Frame-Options"] == "DENY"
    assert "frame-ancestors 'none'" in headers["Content-Security-Policy"]
    assert "max-age" in headers["Strict-Transport-Security"]


def test_unknown_route_returns_json_404(client):
    response = client.get("/does-not-exist")
    assert response.status_code == 404
    assert response.get_json() == {"error": "not found"}


def test_monitoring_is_off_by_default():
    assert app_module.MONITORING_ENABLED is False
