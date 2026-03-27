"""
GCP service account credentials manager.

Authentication flow:
  1. Run `gtaa auth gcp-login --key-file path/to/sa.json --project PROJECT_ID`
     -> validates the key file and caches the path in ~/.gtaa/gcp_credentials.json
  2. Subsequent calls to `get_credentials()` load the service account from the cached path.

Standard GCP env var is also honoured:
  - GOOGLE_APPLICATION_CREDENTIALS pointing to a service account JSON key file
    (used automatically if no cache exists)

Required IAM role on the service account:
  roles/aiplatform.user  (Vertex AI User)
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Optional

CACHE_PATH = Path.home() / ".gtaa" / "gcp_credentials.json"

GCP_SCOPES = ["https://www.googleapis.com/auth/cloud-platform"]


class GCPAuthError(Exception):
    pass


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
# Credentials builders
# ---------------------------------------------------------------------------

def _credentials_from_key_file(key_file: str, project_id: str = ""):
    """Load service account credentials from a JSON key file."""
    from google.oauth2 import service_account  # type: ignore

    key_path = Path(key_file)
    if not key_path.exists():
        raise GCPAuthError(f"Service account key file not found: {key_file}")

    try:
        creds = service_account.Credentials.from_service_account_file(
            str(key_path),
            scopes=GCP_SCOPES,
        )
    except Exception as e:
        raise GCPAuthError(f"Failed to load service account key: {e}") from e

    # quota_project_id directs billing to the configured project
    if project_id:
        creds = creds.with_quota_project(project_id)

    return creds


def _read_sa_email(key_file: str) -> str:
    """Extract service account email from a key JSON without loading credentials."""
    try:
        data = json.loads(Path(key_file).read_text())
        return data.get("client_email", "unknown")
    except Exception:
        return "unknown"


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

class GCPAuthManager:
    """
    Manages GCP service account credentials for Vertex AI.

    Usage:
        manager = GCPAuthManager()
        manager.setup(key_file="path/to/sa.json", project_id="my-project")
        credentials = manager.get_credentials()
    """

    def setup(self, key_file: str, project_id: str) -> None:
        """
        Validate and cache a service account key file.

        Raises GCPAuthError if the key file is invalid or missing.
        """
        key_path = Path(key_file)
        if not key_path.exists():
            raise GCPAuthError(f"Service account key file not found: {key_file}")

        # Validate it's a real service account key
        try:
            data = json.loads(key_path.read_text())
        except (json.JSONDecodeError, OSError) as e:
            raise GCPAuthError(f"Cannot read key file: {e}") from e

        if data.get("type") != "service_account":
            raise GCPAuthError(
                f"Key file must be of type 'service_account', got: {data.get('type', 'unknown')}"
            )

        email = data.get("client_email", "unknown")

        # Optionally do a quick credentials load to validate format
        _credentials_from_key_file(str(key_path), project_id)

        cache = {
            "type": "service_account",
            "key_file": str(key_path.resolve()),
            "project_id": project_id,
            "email": email,
            "method": "service_account",
        }
        _save_cache(cache)

    def get_credentials(self):
        """
        Return valid service account credentials.

        Lookup order:
          1. Cached key file path (~/.gtaa/gcp_credentials.json)
          2. GOOGLE_APPLICATION_CREDENTIALS env var

        Raises GCPAuthError if neither is configured.
        """
        cache = _load_cache()

        if cache and cache.get("type") == "service_account":
            key_file = cache.get("key_file", "")
            project_id = cache.get("project_id", "")
            return _credentials_from_key_file(key_file, project_id)

        # Fall back to GOOGLE_APPLICATION_CREDENTIALS
        adc_path = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS", "")
        if adc_path:
            return _credentials_from_key_file(adc_path)

        raise GCPAuthError(
            "GCP service account not configured.\n"
            "Run: gtaa auth gcp-login --key-file path/to/sa.json --project YOUR_PROJECT_ID\n"
            "Or set: GOOGLE_APPLICATION_CREDENTIALS=path/to/sa.json"
        )

    def get_status(self) -> dict:
        cache = _load_cache()

        if cache and cache.get("type") == "service_account":
            key_file = cache.get("key_file", "")
            # Verify key file still exists
            if not Path(key_file).exists():
                return {
                    "authenticated": False,
                    "message": f"Cached key file no longer exists: {key_file}",
                }
            return {
                "authenticated": True,
                "email": cache.get("email", "unknown"),
                "quota_project_id": cache.get("project_id", ""),
                "method": "service_account",
                "key_file": key_file,
                "message": "Service account credentials configured.",
            }

        # Check env var fallback
        adc_path = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS", "")
        if adc_path and Path(adc_path).exists():
            email = _read_sa_email(adc_path)
            return {
                "authenticated": True,
                "email": email,
                "quota_project_id": "",
                "method": "service_account (GOOGLE_APPLICATION_CREDENTIALS)",
                "key_file": adc_path,
                "message": "Using GOOGLE_APPLICATION_CREDENTIALS env var.",
            }

        return {
            "authenticated": False,
            "message": "No GCP credentials. Run `gtaa auth gcp-login --key-file path/to/sa.json --project PROJECT_ID`.",
        }

    def logout(self) -> None:
        if CACHE_PATH.exists():
            CACHE_PATH.unlink()
