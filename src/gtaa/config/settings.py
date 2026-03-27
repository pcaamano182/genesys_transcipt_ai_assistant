from __future__ import annotations

import os
from pathlib import Path
from typing import List

import yaml
from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# Genesys region → (api host, login host)
# - api host   : used for all REST API calls (conversations, transcripts, etc.)
# - login host : used for OAuth2 authorize + token endpoints
GENESYS_REGIONS: dict[str, tuple[str, str]] = {
    "us_east_1":       ("api.mypurecloud.com",    "login.mypurecloud.com"),
    "us_west_2":       ("api.usw2.pure.cloud",    "login.usw2.pure.cloud"),
    "eu_west_1":       ("api.mypurecloud.ie",     "login.mypurecloud.ie"),
    "eu_west_2":       ("api.euw2.pure.cloud",    "login.euw2.pure.cloud"),
    "ap_southeast_2":  ("api.mypurecloud.com.au", "login.mypurecloud.com.au"),
    "ap_northeast_1":  ("api.mypurecloud.jp",     "login.mypurecloud.jp"),
    "ca_central_1":    ("api.cac1.pure.cloud",    "login.cac1.pure.cloud"),
    "sa_east_1":       ("api.sae1.pure.cloud",    "login.sae1.pure.cloud"),
}


class GenesysSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="GENESYS_")

    region: str = "us_west_2"
    client_id: str = ""
    client_secret: str = ""
    redirect_uri: str = "http://localhost:8080/callback"
    page_size: int = 100

    @field_validator("region")
    @classmethod
    def validate_region(cls, v: str) -> str:
        if v not in GENESYS_REGIONS:
            valid = ", ".join(GENESYS_REGIONS.keys())
            raise ValueError(f"Region '{v}' not valid. Options: {valid}")
        return v

    @property
    def api_base_url(self) -> str:
        return f"https://{GENESYS_REGIONS[self.region][0]}"

    @property
    def login_base_url(self) -> str:
        return f"https://{GENESYS_REGIONS[self.region][1]}"


class GoogleSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="GOOGLE_")

    cloud_project: str = ""
    location: str = "us-central1"
    model: str = "gemini-1.5-pro"
    application_credentials: str = ""

    # OAuth2 Desktop App client — only needed when gcloud CLI is NOT installed.
    # Register a "Desktop app" OAuth2 client in GCP Console → APIs & Services → Credentials.
    oauth_client_id: str = ""
    oauth_client_secret: str = ""

    @property
    def project_id(self) -> str:
        return self.cloud_project


class ProcessingSettings(BaseSettings):
    batch_size: int = 20
    max_workers: int = 5
    max_retries: int = 3
    retry_delay_seconds: float = 2.0
    max_transcript_chars: int = 100_000


class OutputSettings(BaseSettings):
    default_formats: List[str] = ["csv"]
    output_dir: str = "./output"


class Settings:
    """Aggregated application settings loaded from YAML + env vars."""

    def __init__(self, config_path: str | Path | None = None):
        yaml_data = self._load_yaml(config_path)
        self.genesys = GenesysSettings(**(yaml_data.get("genesys", {})))
        self.google = GoogleSettings(**(yaml_data.get("google", {})))
        self.processing = ProcessingSettings(**(yaml_data.get("processing", {})))
        self.output = OutputSettings(**(yaml_data.get("output", {})))

    @staticmethod
    def _load_yaml(config_path: str | Path | None) -> dict:
        if config_path is None:
            default = Path(__file__).parents[4] / "config" / "default.yaml"
            config_path = default if default.exists() else None
        if config_path and Path(config_path).exists():
            with open(config_path, "r", encoding="utf-8") as f:
                return yaml.safe_load(f) or {}
        return {}


_settings_instance: Settings | None = None


def get_settings(config_path: str | Path | None = None) -> Settings:
    global _settings_instance
    if _settings_instance is None:
        _settings_instance = Settings(config_path)
    return _settings_instance


def reset_settings() -> None:
    """Force reload of settings (useful for testing)."""
    global _settings_instance
    _settings_instance = None
