"""Constants for the Målerportal integration."""

DOMAIN = "maalerportal"
SMARTHOME_BASE_URL = "https://api.gateway.meterportal.eu/v1/smarthome"

# Per-request timeout for calls to the gateway, in seconds. Shared by the
# setup check and the config flow so a slow answer is judged the same everywhere.
API_TIMEOUT_SECONDS = 30

# Default polling interval in minutes
DEFAULT_POLLING_INTERVAL = 30
MIN_POLLING_INTERVAL = 15
MAX_POLLING_INTERVAL = 120

# Consumer app. There is no page per installation, only one per meter type,
# so the device link opens the details page for the installation's type.
CONSUMER_APP_URL = "https://consumer.meterportal.eu"
CONSUMER_APP_PATHS = {
    "ColdWater": "/water/details",
    "HotWater": "/hot-water/details",
    "Electricity": "/electricity/details",
    "Heat": "/heating/details",
}


def consumer_app_url(installation_type: str | None) -> str:
    """URL in the consumer app for an installation type, the front page if unknown."""
    return CONSUMER_APP_URL + CONSUMER_APP_PATHS.get(installation_type or "", "/")

# Bookkeeping for entities Målerportal has stopped providing (see sensor.py).
STALE_ENTITIES_STORAGE_VERSION = 1


def stale_entities_storage_key(entry) -> str:
    """Storage key for the per-entry list of entities pending removal."""
    return f"{DOMAIN}.{entry.entry_id}.stale_entities"
