"""
GCP user credentials manager.

Supports two authentication paths (in order of preference):
1. gcloud CLI  — invokes `gcloud auth application-default login` if gcloud is found.
2. OAuth2 Code — uses google-auth-oauthlib to do the full browser flow without gcloud.
                 Requires GCP_OAUTH_CLIENT_ID + GCP_OAUTH_CLIENT_SECRET in config/env.

In both cases the result is a google.oauth2.credentials.Credentials object with
quota_project_id set, so Vertex AI calls are billed to the configured project and
audit logs show the real user email (principalEmail).
"""
from __future__ import annotations

import json
import os
import platform
import shutil
import subprocess
import threading
import time
import webbrowser
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from typing import Optional
from urllib.parse import parse_qs, urlparse

GCP_SCOPES = ["https://www.googleapis.com/auth/cloud-platform"]
CACHE_PATH = Path.home() / ".gtaa" / "gcp_credentials.json"
_GCLOUD_ADC_PATH_WIN = Path(os.environ.get("APPDATA", "")) / "gcloud" / "application_default_credentials.json"
_GCLOUD_ADC_PATH_UNIX = Path.home() / ".config" / "gcloud" / "application_default_credentials.json"
_CALLBACK_PORT = 8081
_AUTH_TIMEOUT = 120


class GCPAuthError(Exception):
    pass


# ---------------------------------------------------------------------------
# gcloud-based path
# ---------------------------------------------------------------------------

def _gcloud_exe() -> Optional[str]:
    """Return path to gcloud executable or None if not installed."""
    return shutil.which("gcloud")


def _gcloud_adc_path() -> Path:
    if platform.system() == "Windows":
        return _GCLOUD_ADC_PATH_WIN
    return _GCLOUD_ADC_PATH_UNIX


def _login_via_gcloud(project_id: str) -> dict:
    """
    Invoke `gcloud auth application-default login` and
    `gcloud auth application-default set-quota-project`.
    Returns the parsed ADC JSON.
    """
    gcloud = _gcloud_exe()
    subprocess.run(
        [gcloud, "auth", "application-default", "login"],
        check=True,
    )
    subprocess.run(
        [gcloud, "auth", "application-default", "set-quota-project", project_id],
        check=True,
    )
    adc_path = _gcloud_adc_path()
    if not adc_path.exists():
        raise GCPAuthError(f"ADC file not found after gcloud login: {adc_path}")
    return json.loads(adc_path.read_text())


def _get_user_email_from_adc(adc_data: dict) -> Optional[str]:
    """Best-effort: get user email from gcloud ADC or token introspection."""
    # gcloud ADC sometimes contains client_id / account info
    # We call the tokeninfo endpoint to resolve the email
    try:
        import httpx
        token = adc_data.get("access_token") or _refresh_gcloud_token(adc_data)
        r = httpx.get(
            "https://www.googleapis.com/oauth2/v3/tokeninfo",
            params={"access_token": token},
            timeout=10,
        )
        if r.status_code == 200:
            return r.json().get("email")
    except Exception:
        pass
    return None


def _refresh_gcloud_token(adc_data: dict) -> Optional[str]:
    """Refresh the gcloud ADC access token using the refresh_token."""
    try:
        import httpx
        r = httpx.post(
            "https://oauth2.googleapis.com/token",
            data={
                "client_id": adc_data["client_id"],
                "client_secret": adc_data["client_secret"],
                "refresh_token": adc_data["refresh_token"],
                "grant_type": "refresh_token",
            },
            timeout=15,
        )
        if r.status_code == 200:
            return r.json().get("access_token")
    except Exception:
        pass
    return None


# ---------------------------------------------------------------------------
# Pure-Python OAuth2 path (no gcloud)
# ---------------------------------------------------------------------------

class _OAuthCallbackHandler(BaseHTTPRequestHandler):
    auth_code: Optional[str] = None
    error: Optional[str] = None

    def do_GET(self):
        params = parse_qs(urlparse(self.path).query)
        if "code" in params:
            _OAuthCallbackHandler.auth_code = params["code"][0]
            self._respond(200, "GCP authentication successful! You can close this tab.")
        elif "error" in params:
            _OAuthCallbackHandler.error = params.get("error_description", params["error"])[0]
            self._respond(400, f"GCP authentication error: {_OAuthCallbackHandler.error}")
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


def _login_via_oauth2(client_id: str, client_secret: str, project_id: str) -> dict:
    """
    Run OAuth2 Authorization Code flow via browser without gcloud.
    Returns a credentials dict suitable for CACHE_PATH.
    """
    from google_auth_oauthlib.flow import Flow  # type: ignore

    redirect_uri = f"http://localhost:{_CALLBACK_PORT}/callback"

    _OAuthCallbackHandler.auth_code = None
    _OAuthCallbackHandler.error = None

    server = HTTPServer(("localhost", _CALLBACK_PORT), _OAuthCallbackHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()

    flow = Flow.from_client_config(
        client_config={
            "installed": {
                "client_id": client_id,
                "client_secret": client_secret,
                "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                "token_uri": "https://oauth2.googleapis.com/token",
                "redirect_uris": [redirect_uri],
            }
        },
        scopes=GCP_SCOPES,
        redirect_uri=redirect_uri,
    )
    auth_url, _ = flow.authorization_url(
        access_type="offline",
        prompt="consent",
        include_granted_scopes="true",
    )

    print("Opening browser for Google Cloud authentication...")
    print(f"If the browser doesn't open, visit:\n  {auth_url}\n")
    webbrowser.open(auth_url)

    deadline = time.time() + _AUTH_TIMEOUT
    while time.time() < deadline:
        if _OAuthCallbackHandler.auth_code or _OAuthCallbackHandler.error:
            break
        time.sleep(0.5)
    server.shutdown()

    if _OAuthCallbackHandler.error:
        raise GCPAuthError(f"GCP auth failed: {_OAuthCallbackHandler.error}")
    if not _OAuthCallbackHandler.auth_code:
        raise GCPAuthError("Timed out waiting for GCP authentication.")

    flow.fetch_token(code=_OAuthCallbackHandler.auth_code)
    creds = flow.credentials

    # Resolve email via tokeninfo
    email = None
    try:
        import httpx
        r = httpx.get(
            "https://www.googleapis.com/oauth2/v3/tokeninfo",
            params={"access_token": creds.token},
            timeout=10,
        )
        if r.status_code == 200:
            email = r.json().get("email")
    except Exception:
        pass

    return {
        "type": "authorized_user",
        "client_id": client_id,
        "client_secret": client_secret,
        "refresh_token": creds.refresh_token,
        "token_uri": "https://oauth2.googleapis.com/token",
        "quota_project_id": project_id,
        "email": email,
    }


# ---------------------------------------------------------------------------
# Cache helpers
# ---------------------------------------------------------------------------

def _save_cache(data: dict) -> None:
    CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
    CACHE_PATH.write_text(json.dumps(data, indent=2))


def _load_cache() -> Optional[dict]:
    if not CACHE_PATH.exists():
        return None
    try:
        return json.loads(CACHE_PATH.read_text())
    except (json.JSONDecodeError, OSError):
        return None


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

class GCPAuthManager:
    """
    Manages GCP user credentials for Vertex AI.
    Tries gcloud first, falls back to direct OAuth2.
    """

    def __init__(self, oauth_client_id: str = "", oauth_client_secret: str = ""):
        self._oauth_client_id = oauth_client_id or os.environ.get("GCP_OAUTH_CLIENT_ID", "")
        self._oauth_client_secret = oauth_client_secret or os.environ.get("GCP_OAUTH_CLIENT_SECRET", "")

    def login(self, project_id: str) -> "google.oauth2.credentials.Credentials":
        """
        Run the login flow. Opens the browser for SSO.
        Returns ready-to-use Credentials with quota_project_id set.
        """
        gcloud = _gcloud_exe()

        if gcloud:
            adc_data = _login_via_gcloud(project_id)
            # Build cache entry from gcloud ADC
            cache = {
                "type": "authorized_user",
                "client_id": adc_data.get("client_id", ""),
                "client_secret": adc_data.get("client_secret", ""),
                "refresh_token": adc_data.get("refresh_token", ""),
                "token_uri": "https://oauth2.googleapis.com/token",
                "quota_project_id": project_id,
                "email": _get_user_email_from_adc(adc_data),
                "method": "gcloud",
            }
        else:
            if not self._oauth_client_id or not self._oauth_client_secret:
                raise GCPAuthError(
                    "gcloud CLI not found and GCP OAuth2 client credentials are not configured.\n"
                    "Options:\n"
                    "  1. Install gcloud CLI: https://cloud.google.com/sdk/docs/install\n"
                    "  2. Set GCP_OAUTH_CLIENT_ID and GCP_OAUTH_CLIENT_SECRET in your .env file\n"
                    "     (register a Desktop App client in GCP Console → APIs & Services → Credentials)"
                )
            cache = _login_via_oauth2(self._oauth_client_id, self._oauth_client_secret, project_id)
            cache["method"] = "oauth2"

        _save_cache(cache)
        return self._credentials_from_cache(cache)

    def get_credentials(self) -> "google.oauth2.credentials.Credentials":
        """
        Return valid credentials from cache. Refreshes automatically if expired.
        Raises GCPAuthError if no cached session exists.
        """
        cache = _load_cache()
        if not cache:
            raise GCPAuthError("Not authenticated. Run `gtaa auth gcp-login --project PROJECT_ID`.")
        return self._credentials_from_cache(cache)

    def get_status(self) -> dict:
        """Return dict with current GCP auth status."""
        cache = _load_cache()
        if not cache:
            return {"authenticated": False, "message": "No GCP session. Run `gtaa auth gcp-login`."}
        return {
            "authenticated": True,
            "email": cache.get("email", "unknown"),
            "quota_project_id": cache.get("quota_project_id", ""),
            "method": cache.get("method", "unknown"),
            "message": "GCP credentials cached.",
        }

    def logout(self) -> None:
        """Remove cached GCP credentials."""
        if CACHE_PATH.exists():
            CACHE_PATH.unlink()

    @staticmethod
    def _credentials_from_cache(cache: dict) -> "google.oauth2.credentials.Credentials":
        from google.oauth2.credentials import Credentials  # type: ignore

        creds = Credentials(
            token=None,  # will be refreshed on first use
            refresh_token=cache.get("refresh_token"),
            token_uri=cache.get("token_uri", "https://oauth2.googleapis.com/token"),
            client_id=cache.get("client_id"),
            client_secret=cache.get("client_secret"),
            quota_project_id=cache.get("quota_project_id"),
            scopes=GCP_SCOPES,
        )
        return creds
