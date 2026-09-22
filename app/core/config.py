"""
Application configuration.

Loads settings from environment variables (via a .env file in local
development, or real environment variables in production/deployment).

No secrets are hardcoded here.
"""

import os
from functools import lru_cache

from dotenv import load_dotenv

# Load variables from a .env file if present. In production, real
# environment variables should be used instead and this becomes a no-op.
load_dotenv()


class Settings:
    """Simple settings container. Values are read once and cached."""

    service_name: str = "ibuum-agent"
    agent_version: str = "0.1"

    def __init__(self) -> None:
        self.ibuum_api_key: str | None = os.getenv("IBUUM_API_KEY")

        # Fail fast in any environment where the key was not configured.
        # This avoids silently running an "open" API.
        if not self.ibuum_api_key:
            raise RuntimeError(
                "IBUUM_API_KEY is not set. Copy .env.example to .env and "
                "set a secure value before starting the service."
            )


@lru_cache
def get_settings() -> Settings:
    """Return a cached Settings instance (loaded once per process)."""
    return Settings()
