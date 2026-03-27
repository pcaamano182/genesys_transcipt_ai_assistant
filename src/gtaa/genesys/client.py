"""
Low-level Genesys Cloud API client using PureCloudPlatformClientV2.
Handles authentication header injection and base URL configuration.
"""
from __future__ import annotations

import PureCloudPlatformClientV2 as gc  # type: ignore

from gtaa.config.settings import GenesysSettings


def build_api_client(access_token: str, settings: GenesysSettings) -> gc.ApiClient:
    """Create and configure a Genesys API client with the given access token."""
    config = gc.Configuration()
    config.host = settings.api_base_url
    config.access_token = access_token

    api_client = gc.ApiClient(configuration=config)
    return api_client
