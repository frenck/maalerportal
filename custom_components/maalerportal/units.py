"""Translate the unit strings the Målerportal API reports into Home Assistant units.

The API's ``unit`` field on a meter counter is free text set by the utility's
import, so the same physical unit shows up in several spellings ("m3", "m³",
"kWh", "KWH", ...). This module normalises those to Home Assistant's unit
constants and decides whether a sensor can keep its device class for that unit.

It only ever translates the label, never the value. If a utility corrects a
counter from m³ to L, the numbers they send are already in litres; Home
Assistant converts the recorded history itself as long as the device class is
kept. A unit the device class cannot handle is shown as-is without a device
class so the mismatch is visible instead of silently mislabelled.
"""

from __future__ import annotations

import logging

from homeassistant.components.sensor import DEVICE_CLASS_UNITS, SensorDeviceClass
from homeassistant.const import (
    UnitOfEnergy,
    UnitOfPower,
    UnitOfVolume,
    UnitOfVolumeFlowRate,
)

_LOGGER = logging.getLogger(__name__)

# L/h has been a Home Assistant flow-rate unit since 2025.6, below the minimum
# version in manifest.json, so flow sensors can always carry the device class.
LITERS_PER_HOUR: str = UnitOfVolumeFlowRate.LITERS_PER_HOUR

# Lower-cased API spellings -> Home Assistant unit. Keys must be lower case.
_API_UNIT_ALIASES: dict[str, str] = {
    # Volume
    "m3": UnitOfVolume.CUBIC_METERS,
    "m³": UnitOfVolume.CUBIC_METERS,
    "m^3": UnitOfVolume.CUBIC_METERS,
    "kubikmeter": UnitOfVolume.CUBIC_METERS,
    "l": UnitOfVolume.LITERS,
    "liter": UnitOfVolume.LITERS,
    "litre": UnitOfVolume.LITERS,
    # Energy
    "wh": UnitOfEnergy.WATT_HOUR,
    "kwh": UnitOfEnergy.KILO_WATT_HOUR,
    "mwh": UnitOfEnergy.MEGA_WATT_HOUR,
    "gj": UnitOfEnergy.GIGA_JOULE,
    "mj": UnitOfEnergy.MEGA_JOULE,
    # Volume flow rate
    "m3/h": UnitOfVolumeFlowRate.CUBIC_METERS_PER_HOUR,
    "m³/h": UnitOfVolumeFlowRate.CUBIC_METERS_PER_HOUR,
    "l/h": LITERS_PER_HOUR,
    "l/min": UnitOfVolumeFlowRate.LITERS_PER_MINUTE,
    # Power
    "w": UnitOfPower.WATT,
    "kw": UnitOfPower.KILO_WATT,
}

# unit_class for imported long-term statistics, per device class we import for.
_STATISTICS_UNIT_CLASS: dict[SensorDeviceClass, str] = {
    SensorDeviceClass.WATER: "volume",
    SensorDeviceClass.ENERGY: "energy",
}


def normalise_api_unit(raw: object) -> str | None:
    """Return the Home Assistant spelling of an API unit.

    Unknown units are returned as sent (stripped), so Home Assistant still shows
    what the utility reported. Missing or blank units return None.
    """
    if raw is None:
        return None
    text = str(raw).strip()
    if not text:
        return None
    return _API_UNIT_ALIASES.get(text.lower(), text)


def resolve_unit(
    counter: dict | None,
    default_unit: str | None,
    device_class: SensorDeviceClass | None,
    *,
    installation_id: str = "",
) -> tuple[str | None, SensorDeviceClass | None]:
    """Choose native unit and device class for a sensor built from an API counter.

    The unit the API reports wins; ``default_unit`` is only used when the API
    reports none. The device class is kept only when Home Assistant accepts the
    chosen unit for it, so statistics and the Energy Dashboard never get a label
    they cannot convert.
    """
    counter = counter or {}
    api_unit = normalise_api_unit(counter.get("unit"))
    unit = api_unit if api_unit is not None else default_unit

    if unit is None or device_class is None:
        return unit, None

    if unit in DEVICE_CLASS_UNITS.get(device_class, ()):
        return unit, device_class

    label = "%s (%s) on installation %s" % (
        counter.get("counterType", "?"),
        counter.get("meterCounterId", "?"),
        installation_id or "?",
    )
    if _is_unit_of_another_device_class(unit, device_class):
        _LOGGER.warning(
            "Counter %s reports unit '%s', which is not a valid %s unit. Showing it "
            "without device class; check the unit on the meter counter at the utility.",
            label,
            unit,
            device_class,
        )
    else:
        _LOGGER.debug(
            "Unit '%s' on counter %s is not supported for %s by this Home Assistant "
            "version; showing it without device class.",
            unit,
            label,
            device_class,
        )
    return unit, None


def statistics_unit_class(device_class: SensorDeviceClass | None) -> str | None:
    """Return the recorder unit_class matching a device class, if we import for it."""
    if device_class is None:
        return None
    return _STATISTICS_UNIT_CLASS.get(device_class)


def _is_unit_of_another_device_class(unit: str, device_class: SensorDeviceClass) -> bool:
    """True when Home Assistant knows the unit, just not for this device class."""
    return any(
        unit in units
        for other_class, units in DEVICE_CLASS_UNITS.items()
        if other_class != device_class and units
    )
