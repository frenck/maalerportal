"""The Målerportal integration."""
from __future__ import annotations

import logging
from typing import Any

import aiohttp
import voluptuous as vol

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers import entity_platform
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.storage import Store

from .api import CannotConnect, InvalidApiKey, validate_api_key
from .const import DOMAIN, STALE_ENTITIES_STORAGE_VERSION, stale_entities_storage_key

_LOGGER = logging.getLogger(__name__)

# List the platforms that you want to support.
PLATFORMS: list[Platform] = [Platform.SENSOR]

# Service constants
SERVICE_REFRESH = "refresh"
ATTR_INSTALLATION_ID = "installation_id"

# Event constants
EVENT_METER_UPDATED = f"{DOMAIN}_meter_updated"

# Service schema
SERVICE_REFRESH_SCHEMA = vol.Schema({
    vol.Optional(ATTR_INSTALLATION_ID): str,
})


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Målerportal from a config entry."""

    # Check the key before any platform runs: Home Assistant only starts the
    # reauth flow for ConfigEntryAuthFailed raised here, not from a platform.
    try:
        await validate_api_key(async_get_clientsession(hass), entry.data["api_key"])
    except InvalidApiKey as err:
        raise ConfigEntryAuthFailed("API key invalid or expired") from err
    except (CannotConnect, aiohttp.ClientError, TimeoutError) as err:
        raise ConfigEntryNotReady(f"Målerportal API not reachable: {err}") from err

    hass.data.setdefault(DOMAIN, {})
    
    # Store the configuration data for sensors to use
    hass.data[DOMAIN][entry.entry_id] = {
        "api_key": entry.data["api_key"],
        "smarthome_base_url": entry.data["smarthome_base_url"],
        "installations": entry.data["installations"],
    }
    
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    
    # Register listener for options updates
    entry.async_on_unload(entry.add_update_listener(async_options_update_listener))

    # Register refresh service (only once)
    if not hass.services.has_service(DOMAIN, SERVICE_REFRESH):
        async def async_refresh_service(call: ServiceCall) -> None:
            """Fetch fresh readings now, ignoring the polling interval."""
            installation_id = call.data.get(ATTR_INSTALLATION_ID)
            _LOGGER.debug("Refresh service called with installation_id: %s", installation_id)

            # Every loaded entry's sensors, not just the entry that registered the service.
            sensors = [
                entity
                for platform in entity_platform.async_get_platforms(hass, DOMAIN)
                for entity in platform.entities.values()
                if installation_id is None or entity.installation_id == installation_id
            ]
            for sensor in sensors:
                await sensor.async_refresh()
            _LOGGER.debug("Refreshed %d entities", len(sensors))

        hass.services.async_register(
            DOMAIN,
            SERVICE_REFRESH,
            async_refresh_service,
            schema=SERVICE_REFRESH_SCHEMA,
        )
        _LOGGER.info("Registered %s.%s service", DOMAIN, SERVICE_REFRESH)

    return True


async def async_remove_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Drop the stale-entity bookkeeping the sensor platform keeps for this entry."""
    await Store(hass, STALE_ENTITIES_STORAGE_VERSION, stale_entities_storage_key(entry)).async_remove()


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        hass.data[DOMAIN].pop(entry.entry_id)
        
        # Unregister service if no more entries
        if not hass.data[DOMAIN]:
            hass.services.async_remove(DOMAIN, SERVICE_REFRESH)
            _LOGGER.info("Unregistered %s.%s service", DOMAIN, SERVICE_REFRESH)

    return unload_ok


async def async_options_update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Handle options update."""
    _LOGGER.info("Options updated, reloading integration")
    await hass.config_entries.async_reload(entry.entry_id)


def fire_meter_updated_event(
    hass: HomeAssistant,
    installation_id: str,
    meter_value: float,
    unit: str,
    timestamp: str | None = None,
    counter_type: str | None = None,
) -> None:
    """Fire an event when meter data is updated."""
    event_data: dict[str, Any] = {
        "installation_id": installation_id,
        "meter_value": meter_value,
        "unit": unit,
    }
    if timestamp:
        event_data["timestamp"] = timestamp
    if counter_type:
        event_data["counter_type"] = counter_type
    
    hass.bus.fire(EVENT_METER_UPDATED, event_data)
    _LOGGER.debug("Fired %s event: %s", EVENT_METER_UPDATED, event_data)
