"""Thin helpers for talking to the Målerportal smarthome API."""

from __future__ import annotations

import aiohttp

from homeassistant.exceptions import HomeAssistantError

from .const import API_TIMEOUT_SECONDS, SMARTHOME_BASE_URL


class CannotConnect(HomeAssistantError):
    """Error to indicate we cannot connect."""


class InvalidApiKey(HomeAssistantError):
    """Error to indicate the API key is invalid."""


class RateLimited(CannotConnect):
    """The gateway is rate limiting us; try again later."""


async def validate_api_key(session: aiohttp.ClientSession, api_key: str) -> None:
    """Validate the API key by calling the addresses endpoint.

    Raises InvalidApiKey on 401 and CannotConnect on any other non-OK response.
    Only 401 means the key is dead: the gateway answers 401 for a missing,
    revoked or expired key. A 403 comes from a gateway or WAF rule and is not
    about the key, so it must not send the user to reauth; it stays on the
    retry path like a network error.
    """
    response = await session.get(
        f"{SMARTHOME_BASE_URL}/addresses",
        headers={"ApiKey": api_key},
        timeout=aiohttp.ClientTimeout(total=API_TIMEOUT_SECONDS),
    )

    if response.status == 401:
        raise InvalidApiKey()
    if response.status == 429:
        raise RateLimited("Rate limit exceeded. Please try again later.")
    if not response.ok:
        error_text = await response.text()
        raise CannotConnect(f"API test failed: HTTP {response.status} - {error_text}")
