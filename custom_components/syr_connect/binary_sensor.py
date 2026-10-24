"""Binary sensor platform for SYR Connect."""

from collections.abc import Callable
from dataclasses import dataclass
import logging
from typing import Any, Literal, override

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .coordinator import SyrConnectDataUpdateCoordinator
from .entity import SyrConnectEntity
from .helpers import get_model_supported_keys, is_value_true, registry_cleanup
from .models import detect_model

_LOGGER = logging.getLogger(__name__)

# Limit parallel updates to avoid overwhelming the API
PARALLEL_UPDATES = 1


# Devices from this device kind (dk) on report flags as True/False instead of 0/1. With the
# change, the sensor settings (getTSD/getPSD/getCSD) flipped their meaning, see
# docs/syrconnect-protocol.md.
_SYR_CONNECT_BINARY_SENSOR_BOOLEAN_API_MIN_DK = 1100


def _is_empty(value: Any) -> bool:
    """Return True for a missing value (None or blank text)."""
    return value is None or str(value).strip() == ""


def _sensor_active(status: dict[str, Any], value: Any) -> bool | None:
    """Return whether a measuring sensor is active (getTSD/getPSD/getCSD).

    Formats:
    - dk < 1100: "0" -> active, "1" -> deactivated
    - dk >= 1100: "True" -> active, "False" -> deactivated

    Args:
        status: Device status, used to detect the model and its device kind (dk)
        value: Raw value of the setting

    Returns:
        True if the sensor is active, False if deactivated, None for an empty value
    """
    if _is_empty(value):
        return None
    dk = detect_model(status).get("dk")
    if isinstance(dk, int) and dk >= _SYR_CONNECT_BINARY_SENSOR_BOOLEAN_API_MIN_DK:
        return is_value_true(value)
    return not is_value_true(value)


@dataclass(frozen=True, kw_only=True)
class SyrConnectBinarySensorEntityDescription(BinarySensorEntityDescription):
    """Describes a SYR Connect binary sensor; `key` is the status key (e.g. "getBUZ")."""

    # Hide the binary sensor while its value is empty (None or blank text)
    hidden_when: Literal["empty"] | None = None
    # Compute the state for keys whose meaning differs from a plain 0/1 flag
    is_on_fn: Callable[[dict[str, Any], Any], bool | None] | None = None


# Descriptions of all binary sensors
_SYR_CONNECT_BINARY_SENSOR_TYPES: tuple[
    SyrConnectBinarySensorEntityDescription, ...
] = (
    SyrConnectBinarySensorEntityDescription(
        key="get71",  # Leak protection deactivated (on = deactivated)
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    SyrConnectBinarySensorEntityDescription(
        key="getBUZ",  # Buzzer on/off
        device_class=BinarySensorDeviceClass.POWER,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    SyrConnectBinarySensorEntityDescription(
        key="getCSD",  # Conductivity sensor active (on = active)
        entity_category=EntityCategory.DIAGNOSTIC,
        hidden_when="empty",
        is_on_fn=_sensor_active,
    ),
    SyrConnectBinarySensorEntityDescription(
        key="getPSD",  # Pressure sensor active (on = active)
        entity_category=EntityCategory.DIAGNOSTIC,
        hidden_when="empty",
        is_on_fn=_sensor_active,
    ),
    SyrConnectBinarySensorEntityDescription(
        key="getSFV",  # New firmware available (checked at startup and every 6 h)
        device_class=BinarySensorDeviceClass.UPDATE,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    SyrConnectBinarySensorEntityDescription(
        key="getTSD",  # Temperature sensor active (on = active)
        entity_category=EntityCategory.DIAGNOSTIC,
        hidden_when="empty",
        is_on_fn=_sensor_active,
    ),
    SyrConnectBinarySensorEntityDescription(
        key="getVTO",  # Valve test running
        device_class=BinarySensorDeviceClass.RUNNING,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
)

_SYR_CONNECT_BINARY_SENSOR_DESCRIPTIONS: dict[
    str, SyrConnectBinarySensorEntityDescription
] = {description.key: description for description in _SYR_CONNECT_BINARY_SENSOR_TYPES}

# Supported keys for the binary_sensor platform — used by registry_cleanup to remove stale entries.
_SYR_CONNECT_BINARY_SENSOR_SUPPORTED_KEYS = set(_SYR_CONNECT_BINARY_SENSOR_DESCRIPTIONS)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up SYR Connect binary sensors.

    Args:
        hass: Home Assistant instance
        entry: Config entry
        async_add_entities: Callback to add entities
    """
    _LOGGER.debug("Setting up SYR Connect binary sensors")
    coordinator: SyrConnectDataUpdateCoordinator = entry.runtime_data

    entities: list[BinarySensorEntity] = []

    if not coordinator.data:
        _LOGGER.warning("No coordinator data available for binary sensors")
        return

    registry_cleanup(
        hass,
        coordinator.data,
        "binary_sensor",
        allowed_keys=_SYR_CONNECT_BINARY_SENSOR_SUPPORTED_KEYS,
        entry_id=coordinator.entry_id,
    )

    for device in coordinator.data.get("devices", []):
        device_id = device["id"]
        device_name = device["name"]
        status = device.get("status", {})
        supported_binary_keys = get_model_supported_keys(
            detect_model(status),
            "binary_sensor",
            _SYR_CONNECT_BINARY_SENSOR_SUPPORTED_KEYS,
        )

        # Create binary sensors for boolean status values
        for description in _SYR_CONNECT_BINARY_SENSOR_TYPES:
            sensor_key = description.key
            if (
                sensor_key in supported_binary_keys
                and sensor_key in status
                and not (
                    description.hidden_when == "empty" and _is_empty(status[sensor_key])
                )
            ):
                entities.append(
                    SyrConnectBinarySensor(
                        coordinator,
                        device_id,
                        device_name,
                        sensor_key,
                    )
                )

    _LOGGER.debug("Adding %d binary sensor(s) total", len(entities))
    async_add_entities(entities)


class SyrConnectBinarySensor(SyrConnectEntity, BinarySensorEntity):
    """Representation of a SYR Connect binary sensor."""

    entity_description: SyrConnectBinarySensorEntityDescription

    def __init__(
        self,
        coordinator: SyrConnectDataUpdateCoordinator,
        device_id: str,
        device_name: str,
        sensor_key: str,
    ) -> None:
        """Initialize the binary sensor.

        Args:
            coordinator: Data update coordinator
            device_id: Device ID (serial number)
            device_name: Device display name
            sensor_key: Sensor key (e.g., 'getBUZ')
        """
        super().__init__(
            coordinator, device_id, device_name, "binary_sensor", sensor_key
        )

        self._sensor_key = sensor_key
        self.entity_description = _SYR_CONNECT_BINARY_SENSOR_DESCRIPTIONS[sensor_key]

    @property
    @override
    def is_on(self) -> bool | None:
        """Return true if the binary sensor is on.

        Returns:
            True if sensor is on, False if off, None if unavailable
        """
        if self._device is None:
            return None
        value = self._status.get(self._sensor_key)
        if self.entity_description.is_on_fn is not None:
            return self.entity_description.is_on_fn(self._status, value)
        # An unknown value (missing, empty) is shown as off
        return is_value_true(value)
