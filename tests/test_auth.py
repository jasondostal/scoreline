"""Auth regression tests — fail-closed behavior.

Auth config is read from env at import time, so each test patches the module
constants directly. main.py imports AUTH_ENABLED by value, so it's patched in
both places. TestClient is used without a context manager so the lifespan
(background pollers, config watcher) never starts.
"""

import auth
import main
import pytest
from fastapi.testclient import TestClient

PROTECTED = "/api/settings"


@pytest.fixture
def configure(monkeypatch):
    """Apply an auth configuration and return a fresh client."""
    def _configure(admin_user="", admin_pass="", api_key="", proxy_header="", trusted_ips=""):
        monkeypatch.setattr(auth, "ADMIN_USER", admin_user)
        monkeypatch.setattr(auth, "ADMIN_PASS", admin_pass)
        monkeypatch.setattr(auth, "API_KEY", api_key)
        monkeypatch.setattr(auth, "AUTH_PROXY_HEADER", proxy_header)
        monkeypatch.setattr(auth, "TRUSTED_PROXY_IPS", trusted_ips)
        login_required = bool(admin_user)
        enabled = login_required or bool(api_key) or bool(proxy_header and trusted_ips)
        monkeypatch.setattr(auth, "LOGIN_REQUIRED", login_required)
        monkeypatch.setattr(auth, "API_AUTH_REQUIRED", bool(api_key))
        monkeypatch.setattr(auth, "AUTH_ENABLED", enabled)
        monkeypatch.setattr(main, "AUTH_ENABLED", enabled)
        monkeypatch.setattr(auth, "_login_attempts", {})
        monkeypatch.setattr(auth, "_sessions", {})
        return TestClient(main.app)
    return _configure


def test_empty_admin_pass_rejects_empty_password(configure):
    client = configure(admin_user="admin", admin_pass="")
    r = client.post("/api/auth/login", json={"username": "admin", "password": ""})
    assert r.status_code == 401
    assert client.get(PROTECTED).status_code == 401


def test_valid_login_grants_session(configure):
    client = configure(admin_user="admin", admin_pass="hunter2")
    assert client.post("/api/auth/login", json={"username": "admin", "password": "nope"}).status_code == 401
    assert client.post("/api/auth/login", json={"username": "admin", "password": "hunter2"}).status_code == 200
    assert client.get("/api/auth/me").json()["authenticated"] is True


def test_proxy_header_only_config_enforces_auth(configure):
    """Proxy-header-only must not leave a direct hit on the port open."""
    client = configure(proxy_header="Remote-User", trusted_ips="10.99.0.0/16")
    assert client.get(PROTECTED).status_code == 401
    # Header from an untrusted source (TestClient is "testclient") is ignored
    assert client.get(PROTECTED, headers={"Remote-User": "mallory"}).status_code == 401


def test_proxy_header_trusted_source_accepted(configure, monkeypatch):
    configure(proxy_header="Remote-User", trusted_ips="10.99.0.0/16")
    monkeypatch.setattr(auth, "_is_trusted_proxy", lambda ip: True)
    user = auth._check_proxy_header(_FakeConn({"Remote-User": "jason"}))
    assert user == "jason"


@pytest.mark.parametrize("path", ["/docs", "/redoc", "/openapi.json"])
def test_api_docs_require_auth(configure, path):
    client = configure(api_key="k")
    assert client.get(path).status_code == 401
    assert client.get(path, headers={"X-API-Key": "k"}).status_code == 200


def test_no_auth_configured_stays_open(configure):
    client = configure()
    assert client.get("/openapi.json").status_code == 200


class _FakeConn:
    def __init__(self, headers):
        self.headers = headers
        self.client = type("C", (), {"host": "10.99.0.5"})()
