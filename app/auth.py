"""Authentication — single-user local auth + reverse proxy bypass + API key."""

import ipaddress
import logging
import os
import secrets
import time
from datetime import UTC, datetime

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from starlette.requests import HTTPConnection
from pydantic import BaseModel

log = logging.getLogger("uvicorn.error")

router = APIRouter()

# In-memory session store — single container, single process, this is fine
_sessions: dict[str, dict] = {}

SESSION_COOKIE = "sl_session"
SESSION_MAX_AGE = 86400 * 7  # 7 days
MAX_SESSIONS = 100

# Rate limiting — per-IP login attempt tracking
_login_attempts: dict[str, list[float]] = {}
RATE_LIMIT_WINDOW = 900  # 15 minutes
RATE_LIMIT_MAX = 5       # max attempts per window


def _secret_or_env(name: str) -> str:
    """Read from Docker secret file first, fall back to env var."""
    secret_file = os.environ.get(f"{name}_SECRETFILE", "")
    if secret_file:
        try:
            return open(secret_file).read().strip()
        except OSError:
            pass
    return os.environ.get(name, "")


# Auth config — read once from env/secrets at import time
ADMIN_USER = os.environ.get("ADMIN_USER", "")
ADMIN_PASS = _secret_or_env("ADMIN_PASS")
AUTH_PROXY_HEADER = os.environ.get("AUTH_PROXY_HEADER", "")
TRUSTED_PROXY_IPS = os.environ.get("TRUSTED_PROXY_IPS", "")
API_KEY = _secret_or_env("API_KEY")
FORCE_HTTPS = bool(os.environ.get("FORCE_HTTPS", ""))

# Derived properties
LOGIN_REQUIRED = bool(ADMIN_USER)
API_AUTH_REQUIRED = bool(API_KEY)
AUTH_ENABLED = LOGIN_REQUIRED or API_AUTH_REQUIRED


class LoginRequest(BaseModel):
    username: str
    password: str


def _is_trusted_proxy(client_ip: str) -> bool:
    """Return True if client_ip matches any entry in TRUSTED_PROXY_IPS (IPs or CIDRs)."""
    if not TRUSTED_PROXY_IPS:
        return False
    try:
        client = ipaddress.ip_address(client_ip)
    except ValueError:
        return False
    for entry in TRUSTED_PROXY_IPS.split(","):
        entry = entry.strip()
        if not entry:
            continue
        try:
            if client in ipaddress.ip_network(entry, strict=False):
                return True
        except ValueError:
            pass
    return False


def _check_proxy_header(request: HTTPConnection) -> str | None:
    """Check if a trusted reverse proxy sent the configured auth header.

    Fail-closed: if AUTH_PROXY_HEADER is set but TRUSTED_PROXY_IPS is not,
    the header is ignored entirely.
    """
    if not AUTH_PROXY_HEADER:
        return None

    header_value = request.headers.get(AUTH_PROXY_HEADER)
    if not header_value:
        return None

    if not TRUSTED_PROXY_IPS:
        log.warning(
            "Proxy header '%s' ignored -- TRUSTED_PROXY_IPS not configured (fail-closed)",
            AUTH_PROXY_HEADER,
        )
        return None

    client_ip = request.client.host if request.client else ""
    if not _is_trusted_proxy(client_ip):
        log.debug(
            "Proxy header '%s' ignored -- source %s not in TRUSTED_PROXY_IPS",
            AUTH_PROXY_HEADER, client_ip,
        )
        return None

    return header_value


def _check_api_key(request: HTTPConnection) -> str | None:
    """Check X-API-Key header with constant-time comparison."""
    if not API_KEY:
        return None
    provided = request.headers.get("X-API-Key", "")
    if provided and secrets.compare_digest(provided, API_KEY):
        return "api"
    return None


def _check_session(request: HTTPConnection) -> str | None:
    """Check if request has a valid session cookie."""
    token = request.cookies.get(SESSION_COOKIE)
    if token and token in _sessions:
        session = _sessions[token]
        if session["expires"] > datetime.now(UTC).timestamp():
            return session["user"]
        del _sessions[token]
    return None


def check_auth(request: HTTPConnection) -> str | None:
    """Check all auth methods. Returns username or None.

    Order: proxy header -> API key -> session cookie.
    If auth is not enabled, returns "anonymous".
    """
    if not AUTH_ENABLED:
        return "anonymous"

    # 1. Proxy header (trusted reverse proxy)
    proxy_user = _check_proxy_header(request)
    if proxy_user:
        return proxy_user

    # 2. API key (programmatic access)
    api_user = _check_api_key(request)
    if api_user:
        return api_user

    # 3. Session cookie (local login)
    session_user = _check_session(request)
    if session_user:
        return session_user

    return None


def log_auth_config():
    """Log auth configuration at startup for visibility."""
    if not AUTH_ENABLED:
        log.info("[AUTH] Authentication disabled (no ADMIN_USER or API_KEY set)")
        return

    methods = []
    if LOGIN_REQUIRED:
        methods.append(f"local login (user={ADMIN_USER})")
    if API_AUTH_REQUIRED:
        methods.append("API key")
    if AUTH_PROXY_HEADER:
        if TRUSTED_PROXY_IPS:
            methods.append(f"proxy header ({AUTH_PROXY_HEADER})")
        else:
            log.warning(
                "[AUTH] AUTH_PROXY_HEADER='%s' set without TRUSTED_PROXY_IPS -- "
                "proxy header auth will be IGNORED (fail-closed)",
                AUTH_PROXY_HEADER,
            )

    log.info("[AUTH] Enabled: %s", " + ".join(methods))


def _check_rate_limit(client_ip: str) -> int | None:
    """Check if client_ip has exceeded login rate limit.

    Returns seconds until retry is allowed, or None if under the limit.
    """
    now = time.monotonic()
    attempts = _login_attempts.get(client_ip, [])
    # Prune attempts outside the window
    attempts = [t for t in attempts if now - t < RATE_LIMIT_WINDOW]
    _login_attempts[client_ip] = attempts

    if len(attempts) >= RATE_LIMIT_MAX:
        oldest_in_window = attempts[0]
        retry_after = int(RATE_LIMIT_WINDOW - (now - oldest_in_window)) + 1
        return retry_after
    return None


def _record_login_attempt(client_ip: str):
    """Record a login attempt for rate limiting."""
    now = time.monotonic()
    _login_attempts.setdefault(client_ip, []).append(now)


def invalidate_all_sessions():
    """Clear all sessions. Use when credentials are rotated."""
    count = len(_sessions)
    _sessions.clear()
    if count:
        log.info("[AUTH] Invalidated %d active sessions", count)


# --- Routes ---

@router.post("/auth/login")
async def login(request: Request, body: LoginRequest):
    """Login with username and password. Returns a session cookie."""
    client_ip = request.client.host if request.client else "unknown"

    if not LOGIN_REQUIRED:
        return {"user": "anonymous", "message": "Auth not configured"}

    # Rate limit check
    retry_after = _check_rate_limit(client_ip)
    if retry_after is not None:
        log.warning("[AUTH] Rate limited login from %s", client_ip)
        return JSONResponse(
            status_code=429,
            content={"detail": "Too many login attempts, try again later"},
            headers={"Retry-After": str(retry_after)},
        )

    if body.username != ADMIN_USER or body.password != ADMIN_PASS:
        _record_login_attempt(client_ip)
        log.warning("[AUTH] Failed login: user=%r from %s", body.username, client_ip)
        return JSONResponse(status_code=401, content={"detail": "Invalid credentials"})

    log.info("[AUTH] Successful login: user=%r from %s", body.username, client_ip)

    # Clean up expired sessions and enforce max count
    now = datetime.now(UTC).timestamp()
    expired = [k for k, v in _sessions.items() if v["expires"] <= now]
    for k in expired:
        del _sessions[k]
    if len(_sessions) >= MAX_SESSIONS:
        return JSONResponse(status_code=429, content={"detail": "Too many active sessions"})

    token = secrets.token_urlsafe(32)
    _sessions[token] = {
        "user": body.username,
        "expires": now + SESSION_MAX_AGE,
    }

    response = JSONResponse(content={"user": body.username})
    response.set_cookie(
        SESSION_COOKIE,
        token,
        max_age=SESSION_MAX_AGE,
        httponly=True,
        samesite="lax",
        secure=FORCE_HTTPS,
        path="/",
    )
    return response


@router.post("/auth/logout")
async def logout(request: Request):
    """Clear session cookie."""
    token = request.cookies.get(SESSION_COOKIE)
    if token and token in _sessions:
        del _sessions[token]

    response = JSONResponse(content={"message": "Logged out"})
    response.delete_cookie(SESSION_COOKIE, path="/")
    return response


@router.get("/auth/me")
async def auth_me(request: Request):
    """Check current auth status. Returns user info or 401."""
    user = check_auth(request)

    if user is None:
        return JSONResponse(status_code=401, content={
            "authenticated": False,
            "login_required": LOGIN_REQUIRED,
        })

    return {
        "authenticated": True,
        "user": user,
        "login_required": LOGIN_REQUIRED,
    }
