"""Config flow for Målerportal integration."""
from __future__ import annotations

import logging
from typing import Any
import aiohttp

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import CannotConnect, InvalidApiKey, RateLimited, validate_api_key
from .const import (
    API_TIMEOUT_SECONDS,
    DOMAIN,
    SMARTHOME_BASE_URL,
    DEFAULT_POLLING_INTERVAL,
    MIN_POLLING_INTERVAL,
    MAX_POLLING_INTERVAL,
)

_LOGGER = logging.getLogger(__name__)

CONF_API_KEY = "api_key"

STEP_API_KEY_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_API_KEY): str,
    }
)

# Meter type translations (Danish as default, since it's a Danish product)
METER_TYPE_TRANSLATIONS = {
    "ColdWater": "Koldt vand",
    "HotWater": "Varmt vand",
    "Electricity": "El",
    "Heat": "Varme",
}


def get_meter_type_label(meter_type: str) -> str:
    """Get translated label for meter type."""
    return METER_TYPE_TRANSLATIONS.get(meter_type, meter_type)


async def _validate_user_input(hass: HomeAssistant, user_input: dict[str, Any]) -> tuple[str | None, str | None]:
    """Validate a submitted API key. Returns (api_key, error_code)."""
    api_key = user_input[CONF_API_KEY].strip()
    if not api_key:
        return None, "invalid_api_key"
    try:
        await validate_api_key(async_get_clientsession(hass), api_key)
        return api_key, None
    except InvalidApiKey:
        return None, "invalid_api_key"
    except RateLimited:
        return None, "rate_limit"
    except CannotConnect:
        return None, "cannot_connect"
    except aiohttp.ClientError:
        return None, "cannot_connect"
    except Exception:
        _LOGGER.exception("Unexpected error validating API key")
        return None, "unknown"


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Målerportal."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize the config flow."""
        self._api_key: str = ""

    @staticmethod
    def async_get_options_flow(config_entry: config_entries.ConfigEntry) -> "OptionsFlow":
        """Get the options flow for this handler."""
        return OptionsFlow()

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the API key input step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            api_key, error = await _validate_user_input(self.hass, user_input)
            if error is None:
                self._api_key = api_key
                return await self.async_step_entity_selection()
            errors["base"] = error

        return self.async_show_form(
            step_id="user",
            data_schema=STEP_API_KEY_SCHEMA,
            errors=errors,
        )

    async def async_step_reauth(
        self, entry_data: dict[str, Any]
    ) -> FlowResult:
        """Triggered when a sensor reports an expired/invalid API key."""
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Prompt for a new API key to replace the expired one."""
        errors: dict[str, str] = {}
        entry = self._get_reauth_entry()

        if user_input is not None:
            api_key, error = await _validate_user_input(self.hass, user_input)
            if error is None:
                return self.async_update_reload_and_abort(
                    entry,
                    data={**entry.data, "api_key": api_key},
                    reason="reauth_successful",
                )
            errors["base"] = error

        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=STEP_API_KEY_SCHEMA,
            errors=errors,
        )

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Let the user replace the API key proactively."""
        errors: dict[str, str] = {}
        entry = self._get_reconfigure_entry()

        if user_input is not None:
            api_key, error = await _validate_user_input(self.hass, user_input)
            if error is None:
                return self.async_update_reload_and_abort(
                    entry,
                    data={**entry.data, "api_key": api_key},
                    reason="reconfigure_successful",
                )
            errors["base"] = error

        return self.async_show_form(
            step_id="reconfigure",
            data_schema=STEP_API_KEY_SCHEMA,
            errors=errors,
        )

    async def async_step_entity_selection(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle selection of installations step."""
        errors: dict[str, str] = {}
        if user_input is not None:
            installations: list[dict] = self.context["installationdata"]
            save_data: dict[str, Any] = {
                "installations": [],
                "api_key": self._api_key,
                "smarthome_base_url": SMARTHOME_BASE_URL,
            }
            for k in user_input["entity_selection"]:
                for installation in installations:
                    if installation["installationId"] == k:
                        save_data["installations"].append(installation)
                        break
            return self.async_create_entry(title="Målere", data=save_data)

        entities_with_labels: dict[str, str] = {}
        try:
            session = async_get_clientsession(self.hass)
            addresses_response = await session.get(
                f"{SMARTHOME_BASE_URL}/addresses",
                headers={"ApiKey": self._api_key},
                timeout=aiohttp.ClientTimeout(total=API_TIMEOUT_SECONDS),
            )

            if addresses_response.status == 429:
                errors["base"] = "rate_limit"
            elif not addresses_response.ok:
                errors["base"] = "cannot_connect"
            else:
                addresses = await addresses_response.json()
                installations = []

                for address in addresses:
                    for installation in address.get("installations", []):
                        installation_id = installation.get("installationId")
                        utility_name = installation.get("utilityName", "Unknown")
                        installation_type = installation.get("installationType", "Unknown")
                        meter_serial = installation.get("meterSerial", "Unknown")
                        nickname = installation.get("nickname", "")

                        device_name = f"{address.get('address', 'Unknown')} - {meter_serial}"
                        if nickname:
                            device_name += f" ({nickname})"

                        meter_type_label = get_meter_type_label(installation_type)
                        entities_with_labels[installation_id] = f"{device_name} [{meter_type_label}]"

                        installations.append({
                            "installationId": installation_id,
                            "address": address.get("address"),
                            "timezone": address.get("timezone"),
                            "installationType": installation_type,
                            "utilityName": utility_name,
                            "meterSerial": meter_serial,
                            "nickname": nickname,
                        })

                self.context["installationdata"] = installations

                if not entities_with_labels:
                    errors["base"] = "no_meters"

        except aiohttp.ClientError:
            errors["base"] = "cannot_connect"
        except Exception:
            _LOGGER.exception("Unexpected error fetching installations")
            errors["base"] = "unknown"

        if errors.get("base") == "no_meters":
            return self.async_show_form(
                step_id="entity_selection",
                data_schema=vol.Schema({}),
                errors=errors,
            )

        return self.async_show_form(
            step_id="entity_selection",
            data_schema=vol.Schema(
                {
                    vol.Optional("entity_selection"): cv.multi_select(
                        entities_with_labels
                    )
                },
                extra=vol.ALLOW_EXTRA,
            ),
            errors=errors,
        )


class OptionsFlow(config_entries.OptionsFlow):
    """Handle options flow for Målerportal."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Manage the options."""
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        current_interval = self.config_entry.options.get(
            "polling_interval", DEFAULT_POLLING_INTERVAL
        )

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Optional(
                        "polling_interval",
                        default=current_interval,
                    ): vol.All(
                        vol.Coerce(int),
                        vol.Range(min=MIN_POLLING_INTERVAL, max=MAX_POLLING_INTERVAL),
                    ),
                }
            ),
        )
