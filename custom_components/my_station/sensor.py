"""Sensor platform for My Station."""

from __future__ import annotations

from typing import Any

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_NAME
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import MyStationDataUpdateCoordinator

ATTRIBUTION = "Data provided by Rejseplanen"


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the departures sensor from a config entry."""
    coordinator: MyStationDataUpdateCoordinator = hass.data[DOMAIN][
        config_entry.entry_id
    ]
    async_add_entities([MyStationDeparturesSensor(coordinator, config_entry)])


class MyStationDeparturesSensor(
    CoordinatorEntity[MyStationDataUpdateCoordinator], SensorEntity
):
    """Represent a compact Rejseplanen departure board."""

    _attr_has_entity_name = True
    _attr_translation_key = "departures"
    _attr_icon = "mdi:train-clock"
    _attr_attribution = ATTRIBUTION

    def __init__(
        self,
        coordinator: MyStationDataUpdateCoordinator,
        config_entry: ConfigEntry,
    ) -> None:
        """Initialize the departures sensor."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{config_entry.entry_id}_departures"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, config_entry.entry_id)},
            name=config_entry.data[CONF_NAME],
            manufacturer="Rejseplanen",
            model="Departure board",
        )

    @property
    def native_value(self) -> int:
        """Return the current number of compact departure rows."""
        return int(self.coordinator.data["count"])

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Expose the compact payload consumed by the Lovelace card."""
        return self.coordinator.data
