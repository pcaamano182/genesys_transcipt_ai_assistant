"""Google Cloud authentication helpers."""
from __future__ import annotations

import os
from typing import Optional


def init_vertex_ai(
    project_id: str,
    location: str,
    credentials=None,
) -> None:
    """
    Initialize Vertex AI SDK.

    When `credentials` is a google.oauth2.credentials.Credentials object
    (user credentials with quota_project_id set), Vertex AI calls will be
    attributed to that user in Cloud Audit Logs.
    """
    import vertexai  # type: ignore

    vertexai.init(project=project_id, location=location, credentials=credentials)


def get_project_id(google_settings) -> str:
    """Resolve GCP project ID from settings or environment."""
    project = google_settings.project_id or os.environ.get("GOOGLE_CLOUD_PROJECT", "")
    if not project:
        raise ValueError(
            "Google Cloud project ID is required. "
            "Set GOOGLE_CLOUD_PROJECT env var or 'google.project_id' in config."
        )
    return project
