"""
Genesys Cloud OAuth2 authentication.

Supports two grant types (auto-selected via GENESYS_GRANT_TYPE):

  client_credentials  (default)
    - No browser, no redirect URI required.
    - Uses client_id + client_secret directly to get an access token.
    - Token expires in ~1 day; refreshed automatically on next use.
    - Use this when you have credentials from Admin -> Integrations -> OAuth
      with grant type "Client Credentials".

  authorization_code
    - Opens a browser for the user to log in interactively.
    - Requires a redirect URI registered in the Genesys OAuth app.
    - Use this when the OAuth app was created with grant type "Code Authorization".
"""
from __future__ import annotations

import json
import secrets
import threading
import time
import webbrowser
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from typing import Optional
from urllib.parse import parse_qs, urlencode, urlparse

import httpx

from gtaa.config.settings import GenesysSettings

TOKEN_CACHE_PATH = Path.home() / ".gtaa" / "tokens.json"
_AUTH_TIMEOUT = 120


class GenesysAuthError(Exception):
    pass


# ---------------------------------------------------------------------------
# Client Credentials flow
# ---------------------------------------------------------------------------

def _login_client_credentials(settings: GenesysSettings) -> dict:
    """
    POST client_id + client_secret directly to get an access token.
    No browser, no redirect URI needed.
    """
    token_url = f"{settings.login_base_url}/oauth/token"
    response = httpx.post(
        token_url,
        data={"grant_type": "client_credentials"},
        auth=(settings.client_id, settings.client_secret),
        timeout=30,
    )
    if response.status_code != 200:
        raise GenesysAuthError(
            f"Client credentials login failed ({response.status_code}): {response.text}"
        )
    return response.json()


# ---------------------------------------------------------------------------
# Authorization Code flow
# ---------------------------------------------------------------------------

class _CallbackHandler(BaseHTTPRequestHandler):
    auth_code: Optional[str] = None
    error: Optional[str] = None

    def do_GET(self):
        params = parse_qs(urlparse(self.path).query)
        if "code" in params:
            _CallbackHandler.auth_code = params["code"][0]
            self._respond(200, "Authentication successful! You can close this tab.")
        elif "error" in params:
            _CallbackHandler.error = params.get("error_description", params["error"])[0]
            self._respond(400, f"Authentication error: {_CallbackHandler.error}")
        else:
            self._respond(404, "Not found")

    def _respond(self, code: int, message: str):
        body = f"<html><body><h2>{message}</h2></body></html>".encode()
        self.send_response(code)
        self.send_header("Content-Type", "text/html")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args):
        pass


def _exchange_code(code: str, settings: GenesysSettings) -> dict:
    token_url = f"{settings.login_base_url}/oauth/token"
    response = httpx.post(
        token_url,
        data={
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": settings.redirect_uri,
        },
        auth=(settings.client_id, settings.client_secret),
        timeout=30,
    )
    if response.status_code != 200:
        raise GenesysAuthError(
            f"Token exchange failed ({response.status_code}): {response.text}"
        )
    return response.json()


def _login_authorization_code(settings: GenesysSettings) -> dict:
    """Opens browser, waits for callback, exchanges code for token."""
    port = int(urlparse(settings.redirect_uri).port or 8080)

    _CallbackHandler.auth_code = None
    _CallbackHandler.error = None

    state = secrets.token_urlsafe(16)
    params = urlencode({
        "response_type": "code",
        "client_id": settings.client_id,
        "redirect_uri": settings.redirect_uri,
        "state": state,
    })
    auth_url = f"{settings.login_base_url}/oauth/authorize?{params}"

    server = HTTPServer(("localhost", port), _CallbackHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()

    print("Opening browser for Genesys authentication...")
    print(f"If the browser doesn't open, visit:\n  {auth_url}\n")
    webbrowser.open(auth_url)

    deadline = time.time() + _AUTH_TIMEOUT
    while time.time() < deadline:
        if _CallbackHandler.auth_code or _CallbackHandler.error:
            break
        time.sleep(0.5)
    server.shutdown()

    if _CallbackHandler.error:
        raise GenesysAuthError(f"Auth failed: {_CallbackHandler.error}")
    if not _CallbackHandler.auth_code:
        raise GenesysAuthError("Timed out waiting for authentication.")

    return _exchange_code(_CallbackHandler.auth_code, settings)


# ---------------------------------------------------------------------------
# Refresh token (Authorization Code only)
# ---------------------------------------------------------------------------

def _refresh_token(refresh_tok: str, settings: GenesysSettings) -> dict:
    token_url = f"{settings.login_base_url}/oauth/token"
    response = httpx.post(
        token_url,
        data={
            "grant_type": "refresh_token",
            "refresh_token": refresh_tok,
        },
        auth=(settings.client_id, settings.client_secret),
        timeout=30,
    )
    if response.status_code != 200:
        raise GenesysAuthError(
            f"Token refresh failed ({response.status_code}): {response.text}"
        )
    return response.json()


# ---------------------------------------------------------------------------
# Token cache
# ---------------------------------------------------------------------------

def _save_tokens(token_data: dict, grant_type: str) -> None:
    TOKEN_CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
    expires_at = time.time() + token_data.get("expires_in", 86400)
    cache = {
        "access_token": token_data["access_token"],
        "refresh_token": token_data.get("refresh_token", ""),
        "expires_at": expires_at,
        "token_type": token_data.get("token_type", "bearer"),
        "grant_type": grant_type,
    }
    TOKEN_CACHE_PATH.write_text(json.dumps(cache, indent=2))


def _load_tokens() -> Optional[dict]:
    if not TOKEN_CACHE_PATH.exists():
        return None
    try:
        return json.loads(TOKEN_CACHE_PATH.read_text())
    except (json.JSONDecodeError, OSError):
        return None


def _is_expired(tokens: dict, buffer_seconds: int = 60) -> bool:
    return time.time() >= tokens.get("expires_at", 0) - buffer_seconds


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def login(settings: GenesysSettings) -> str:
    """
    Authenticate and return an access token.
    Chooses the flow based on settings.grant_type.
    """
    if settings.grant_type == "client_credentials":
        token_data = _login_client_credentials(settings)
    else:
        token_data = _login_authorization_code(settings)

    _save_tokens(token_data, settings.grant_type)
    return token_data["access_token"]


def get_access_token(settings: GenesysSettings) -> str:
    """
    Return a valid access token from cache, refreshing or re-authenticating as needed.
    """
    tokens = _load_tokens()

    if tokens and not _is_expired(tokens):
        return tokens["access_token"]

    # Client Credentials: no refresh token, just re-authenticate silently
    if settings.grant_type == "client_credentials":
        return login(settings)

    # Authorization Code: try refresh token first
    if tokens and tokens.get("refresh_token"):
        try:
            token_data = _refresh_token(tokens["refresh_token"], settings)
            _save_tokens(token_data, settings.grant_type)
            return token_data["access_token"]
        except GenesysAuthError:
            pass

    return login(settings)


def get_token_status() -> dict:
    tokens = _load_tokens()
    if not tokens:
        return {"authenticated": False, "message": "No cached tokens. Run `gtaa auth login`."}
    expired = _is_expired(tokens)
    expires_dt = datetime.fromtimestamp(tokens["expires_at"], tz=timezone.utc)
    return {
        "authenticated": not expired,
        "expires_at": expires_dt.isoformat(),
        "expired": expired,
        "grant_type": tokens.get("grant_type", "unknown"),
        "has_refresh_token": bool(tokens.get("refresh_token")),
        "message": "Token is valid." if not expired else "Token expired. Will refresh on next use.",
    }
