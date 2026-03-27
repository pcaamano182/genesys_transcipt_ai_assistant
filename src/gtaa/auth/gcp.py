"""
GCP user credentials manager.

Authentication priority (fully automatic, no user configuration needed):

  1. gcloud CLI installed
       -> runs `gcloud auth application-default login`
       -> browser opens, user logs in with SSO (Okta, Azure AD, etc.)
       -> credentials managed by gcloud

  2. gcloud NOT installed
       -> uses the Google Cloud SDK public OAuth2 client (open-source, same
          client ID embedded in gcloud itself) to run the identical browser flow
       -> user sees the exact same Google login page
       -> credentials cached in ~/.gtaa/gcp_credentials.json

In both cases:
  - Zero extra configuration required from the user
  - SSO (Okta, Azure AD federated to Google) works transparently
  - Vertex AI calls appear in Cloud Audit Logs with the user's email
  - quota_project_id ties billing to the configured GCP project
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
from pathlib import Path
from typing import Optional
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import parse_qs, urlparse

GCP_SCOPES = ["https://www.googleapis.com/auth/cloud-platform"]
CACHE_PATH = Path.home() / ".gtaa" / "gcp_credentials.json"

_GCLOUD_ADC_PATH_WIN  = Path(os.environ.get("APPDATA", "")) / "gcloud" / "application_default_credentials.json"
_GCLOUD_ADC_PATH_UNIX = Path.home() / ".config" / "gcloud" / "application_default_credentials.json"

_CALLBACK_PORT = 8081
_AUTH_TIMEOUT  = 120

# ---------------------------------------------------------------------------
# Google Cloud SDK public OAuth2 client
# These credentials are open-source and publicly embedded in the gcloud SDK:
# https://github.com/google-cloud-sdk-unofficial/google-cloud-sdk (lib/googlecloudsdk/core/credentials)
# Using them produces the identical browser login experience as `gcloud auth application-default login`.
# ---------------------------------------------------------------------------
_GCLOUD_CLIENT_ID     = "764086051850-6qr4p6gpi6hn506pt8ejuq83di341hur.apps.googleusercontent.com"
_GCLOUD_CLIENT_SECRET = "d-FL95Q19q7MQmFpd7hHD0Ty"  # noqa: S105 — public value, not a real secret


class GCPAuthError(Exception):
    pass


# ---------------------------------------------------------------------------
# Path 1: gcloud CLI
# ---------------------------------------------------------------------------

def _gcloud_exe() -> Optional[str]:
    return shutil.which("gcloud")


def _gcloud_adc_path() -> Path:
    return _GCLOUD_ADC_PATH_WIN if platform.system() == "Windows" else _GCLOUD_ADC_PATH_UNIX


def _login_via_gcloud(project_id: str) -> dict:
    gcloud = _gcloud_exe()
    subprocess.run([gcloud, "auth", "application-default", "login"], check=True)
    subprocess.run([gcloud, "auth", "application-default", "set-quota-project", project_id], check=True)
    adc_path = _gcloud_adc_path()
    if not adc_path.exists():
        raise GCPAuthError(f"ADC file not found after gcloud login: {adc_path}")
    return json.loads(adc_path.read_text())


# ---------------------------------------------------------------------------
# Path 2: browser OAuth2 flow without gcloud
# ---------------------------------------------------------------------------

class _CallbackHandler(BaseHTTPRequestHandler):
    auth_code: Optional[str] = None
    error: Optional[str] = None

    def do_GET(self):
        params = parse_qs(urlparse(self.path).query)
        if "code" in params:
            _CallbackHandler.auth_code = params["code"][0]
            self._respond(200, "Google authentication successful! You can close this tab.")
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


def _login_via_browser(project_id: str, client_id: str, client_secret: str) -> dict:
    """
    Run OAuth2 Authorization Code flow in the browser using the provided
    (or default gcloud SDK) client credentials.
    Returns a cache dict ready to save.
    """
    from google_auth_oauthlib.flow import Flow  # type: ignore

    redirect_uri = f"http://localhost:{_CALLBACK_PORT}/callback"

    _CallbackHandler.auth_code = None
    _CallbackHandler.error = None

    server = HTTPServer(("localhost", _CALLBACK_PORT), _CallbackHandler)
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
    auth_url, _ = flow.authorization_url(access_type="offline", prompt="consent")

    print("Opening browser for Google Cloud authentication...")
    print(f"If the browser does not open automatically, visit:\n  {auth_url}\n")
    webbrowser.open(auth_url)

    deadline = time.time() + _AUTH_TIMEOUT
    while time.time() < deadline:
        if _CallbackHandler.auth_code or _CallbackHandler.error:
            break
        time.sleep(0.5)
    server.shutdown()

    if _CallbackHandler.error:
        raise GCPAuthError(f"GCP auth failed: {_CallbackHandler.error}")
    if not _CallbackHandler.auth_code:
        raise GCPAuthError("Timed out waiting for Google authentication.")

    flow.fetch_token(code=_CallbackHandler.auth_code)
    creds = flow.credentials

    # Resolve the authenticated user's email
    email = _resolve_email(creds.token)

    return {
        "type": "authorized_user",
        "client_id": client_id,
        "client_secret": client_secret,
        "refresh_token": creds.refresh_token,
        "token_uri": "https://oauth2.googleapis.com/token",
        "quota_project_id": project_id,
        "email": email,
        "method": "browser",
    }


def _resolve_email(access_token: str) -> Optional[str]:
    try:
        import httpx
        r = httpx.get(
            "https://www.googleapis.com/oauth2/v3/tokeninfo",
            params={"access_token": access_token},
            timeout=10,
        )
        if r.status_code == 200:
            return r.json().get("email")
    except Exception:
        pass
    return None


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


def _credentials_from_cache(cache: dict):
    from google.oauth2.credentials import Credentials  # type: ignore
    return Credentials(
        token=None,
        refresh_token=cache.get("refresh_token"),
        token_uri=cache.get("token_uri", "https://oauth2.googleapis.com/token"),
        client_id=cache.get("client_id"),
        client_secret=cache.get("client_secret"),
        quota_project_id=cache.get("quota_project_id"),
        scopes=GCP_SCOPES,
    )


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

class GCPAuthManager:
    """
    Manages GCP user credentials for Vertex AI.

    Authentication is fully automatic:
    - If gcloud CLI is installed, uses it (preferred).
    - Otherwise, opens a browser using the embedded Google Cloud SDK OAuth client —
      same experience as gcloud, no extra user configuration needed.

    Custom OAuth client credentials (GCP_OAUTH_CLIENT_ID / GCP_OAUTH_CLIENT_SECRET)
    are supported as an optional override for organisations that prefer
    to use their own registered app.
    """

    def __init__(self, oauth_client_id: str = "", oauth_client_secret: str = ""):
        # Use provided credentials or fall back to the embedded gcloud SDK client
        self._client_id     = oauth_client_id     or os.environ.get("GCP_OAUTH_CLIENT_ID", "")     or _GCLOUD_CLIENT_ID
        self._client_secret = oauth_client_secret or os.environ.get("GCP_OAUTH_CLIENT_SECRET", "") or _GCLOUD_CLIENT_SECRET

    def login(self, project_id: str):
        """Run login flow. Opens browser for SSO. Returns ready-to-use Credentials."""
        gcloud = _gcloud_exe()

        if gcloud:
            adc = _login_via_gcloud(project_id)
            cache = {
                "type": "authorized_user",
                "client_id": adc.get("client_id", self._client_id),
                "client_secret": adc.get("client_secret", self._client_secret),
                "refresh_token": adc.get("refresh_token", ""),
                "token_uri": "https://oauth2.googleapis.com/token",
                "quota_project_id": project_id,
                "email": _resolve_email(_refresh_access_token(
                    adc.get("refresh_token", ""),
                    adc.get("client_id", self._client_id),
                    adc.get("client_secret", self._client_secret),
                ) or ""),
                "method": "gcloud",
            }
        else:
            cache = _login_via_browser(project_id, self._client_id, self._client_secret)

        _save_cache(cache)
        return _credentials_from_cache(cache)

    def get_credentials(self):
        """Return valid credentials from cache. Raises GCPAuthError if not logged in."""
        cache = _load_cache()
        if not cache:
            raise GCPAuthError(
                "Not authenticated with Google Cloud.\n"
                "Run: gtaa auth gcp-login --project YOUR_PROJECT_ID"
            )
        return _credentials_from_cache(cache)

    def get_status(self) -> dict:
        cache = _load_cache()
        if not cache:
            return {"authenticated": False, "message": "No GCP session. Run `gtaa auth gcp-login`."}
        return {
            "authenticated": True,
            "email": cache.get("email", "unknown"),
            "quota_project_id": cache.get("quota_project_id", ""),
            "method": cache.get("method", "browser"),
            "message": "GCP credentials cached.",
        }

    def logout(self) -> None:
        if CACHE_PATH.exists():
            CACHE_PATH.unlink()


def _refresh_access_token(refresh_token: str, client_id: str, client_secret: str) -> Optional[str]:
    """Exchange a refresh token for a new access token (used only to resolve email after gcloud login)."""
    try:
        import httpx
        r = httpx.post(
            "https://oauth2.googleapis.com/token",
            data={
                "grant_type": "refresh_token",
                "refresh_token": refresh_token,
                "client_id": client_id,
                "client_secret": client_secret,
            },
            timeout=15,
        )
        if r.status_code == 200:
            return r.json().get("access_token")
    except Exception:
        pass
    return None
