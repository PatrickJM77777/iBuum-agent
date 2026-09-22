"""
Simple API key authentication.

The training endpoint is protected with a static API key sent in the
`X-API-Key` header. The key is never hardcoded; it is loaded from the
IBUUM_API_KEY environment variable via app.core.config.
"""

from fastapi import Header, HTTPException, status

from app.core.config import get_settings


async def verify_api_key(x_api_key: str | None = Header(default=None)) -> None:
    """
    FastAPI dependency that validates the X-API-Key header.

    Raises 401 if the header is missing or does not match the configured key.
    """
    settings = get_settings()

    if not x_api_key or x_api_key != settings.ibuum_api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing API key.",
        )
