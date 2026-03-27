"""
Genesys Cloud OAuth2 Authorization Code flow.

Flow:
1. Build authorization URL and open it in the browser.
2. Start a local HTTP server to capture the redirect with ?code=...
3. Exchange the code for access + refresh tokens.
4. Cache tokens to ~/.gtaa/tokens.json.
5. On subsequent calls, load from cache and refresh if expired.
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
_AUTH_TIMEOUT = 120  # seconds to wait for browser auth


class GenesysAuthError(Exception):
    pass


class _CallbackHandler(BaseHTTPRequestHandler):
    """Minimal HTTP handler to capture OAuth2 callback."""

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
        pass  # suppress server logs


def _start_callback_server(port: int) -> HTTPServer:
    server = HTTPServer(("localhost", port), _CallbackHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server


def _exchange_code(
    code: str,
    settings: GenesysSettings,
    state: str,
) -> dict:
    redirect_uri = settings.redirect_uri
    token_url = f"{settings.api_base_url}/oauth/token"
    response = httpx.post(
        token_url,
        data={
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": redirect_uri,
        },
        auth=(settings.client_id, settings.client_secret),
        timeout=30,
    )
    if response.status_code != 200:
        raise GenesysAuthError(
            f"Token exchange failed ({response.status_code}): {response.text}"
        )
    return response.json()


def _refresh_token(refresh_tok: str, settings: GenesysSettings) -> dict:
    token_url = f"{settings.api_base_url}/oauth/token"
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


def _save_tokens(token_data: dict) -> None:
    TOKEN_CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
    expires_at = time.time() + token_data.get("expires_in", 86400)
    cache = {
        "access_token": token_data["access_token"],
        "refresh_token": token_data.get("refresh_token", ""),
        "expires_at": expires_at,
        "token_type": token_data.get("token_type", "bearer"),
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


def login(settings: GenesysSettings) -> str:
    """
    Run the Authorization Code flow. Opens the browser, waits for callback,
    exchanges code, saves tokens. Returns the access token.
    """
    from urllib.parse import urlparse

    port = int(urlparse(settings.redirect_uri).port or 8080)

    _CallbackHandler.auth_code = None
    _CallbackHandler.error = None

    state = secrets.token_urlsafe(16)
    params = urlencode(
        {
            "response_type": "code",
            "client_id": settings.client_id,
            "redirect_uri": settings.redirect_uri,
            "state": state,
        }
    )
    auth_url = f"{settings.api_base_url}/oauth/authorize?{params}"

    server = _start_callback_server(port)
    print(f"Opening browser for Genesys authentication...")
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

    token_data = _exchange_code(_CallbackHandler.auth_code, settings, state)
    _save_tokens(token_data)
    return token_data["access_token"]


def get_access_token(settings: GenesysSettings) -> str:
    """
    Return a valid access token, refreshing or re-authenticating as needed.
    """
    tokens = _load_tokens()

    if tokens and not _is_expired(tokens):
        return tokens["access_token"]

    if tokens and tokens.get("refresh_token"):
        try:
            token_data = _refresh_token(tokens["refresh_token"], settings)
            _save_tokens(token_data)
            return token_data["access_token"]
        except GenesysAuthError:
            pass  # fall through to full login

    return login(settings)


def get_token_status() -> dict:
    """Return current token status for `gtaa auth status`."""
    tokens = _load_tokens()
    if not tokens:
        return {"authenticated": False, "message": "No cached tokens found. Run `gtaa auth login`."}
    expired = _is_expired(tokens)
    expires_dt = datetime.fromtimestamp(tokens["expires_at"], tz=timezone.utc)
    return {
        "authenticated": not expired,
        "expires_at": expires_dt.isoformat(),
        "expired": expired,
        "has_refresh_token": bool(tokens.get("refresh_token")),
        "message": "Token is valid." if not expired else "Token expired. Will auto-refresh on next use.",
    }
