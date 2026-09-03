"""The My Station integration."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from homeassistant.components.http import StaticPathConfig
from homeassistant.components.lovelace.const import (
    CONF_RESOURCE_TYPE_WS,
    LOVELACE_DATA,
    MODE_STORAGE,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_ID, CONF_TYPE, CONF_URL, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv
from homeassistant.loader import async_get_integration

from .const import CARD_RESOURCE_URL, CARD_URL_PATH, DOMAIN
from .coordinator import MyStationDataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [Platform.SENSOR]
CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)


async def async_setup(hass: HomeAssistant, _config: dict[str, Any]) -> bool:
    """Serve and register the bundled Lovelace card."""
    frontend_path = Path(__file__).parent / "frontend"
    await hass.http.async_register_static_paths(
        [StaticPathConfig(CARD_URL_PATH, str(frontend_path), False)]
    )

    try:
        await _async_register_card_resource(hass)
    except Exception:  # pragma: no cover - registration is best-effort
        _LOGGER.exception(
            "Failed to register the My Station dashboard resource. Add %s "
            "manually as a JavaScript module",
            CARD_RESOURCE_URL,
        )
    return True


def _lovelace_value(data: Any, name: str) -> Any:
    """Read a field from current or legacy Lovelace data."""
    if isinstance(data, dict):
        return data.get(name)
    return getattr(data, name, None)


async def _async_register_card_resource(hass: HomeAssistant) -> None:
    """Create or update the card's Lovelace resource in storage mode."""
    lovelace_data = hass.data.get(LOVELACE_DATA)
    if lovelace_data is None:
        _LOGGER.warning(
            "Lovelace is unavailable. Add %s manually as a JavaScript module",
            CARD_RESOURCE_URL,
        )
        return

    resource_mode = _lovelace_value(lovelace_data, "resource_mode")
    if resource_mode is None:
        resource_mode = _lovelace_value(lovelace_data, "mode")
    if resource_mode != MODE_STORAGE:
        _LOGGER.info(
            "Lovelace resources are managed in %s mode. Add %s to the YAML "
            "resource list as a JavaScript module",
            resource_mode,
            CARD_RESOURCE_URL,
        )
        return

    resources = _lovelace_value(lovelace_data, "resources")
    if resources is None or not hasattr(resources, "async_create_item"):
        _LOGGER.warning(
            "The Lovelace resource collection is not writable. Add %s "
            "manually as a JavaScript module",
            CARD_RESOURCE_URL,
        )
        return

    # Loading first prevents an empty in-memory collection from causing a
    # duplicate entry or overwriting stored resources on older HA releases.
    await resources.async_get_info()

    integration = await async_get_integration(hass, DOMAIN)
    resource_url = f"{CARD_RESOURCE_URL}?v={integration.version}"
    matches = [
        item
        for item in resources.async_items()
        if str(item.get(CONF_URL, "")).partition("?")[0] == CARD_RESOURCE_URL
    ]

    if not matches:
        created = await resources.async_create_item(
            {CONF_RESOURCE_TYPE_WS: "module", CONF_URL: resource_url}
        )
        _LOGGER.info(
            "Registered My Station dashboard resource %s (%s)",
            created.get(CONF_ID),
            resource_url,
        )
        return

    resource = matches[0]
    updates: dict[str, str] = {}
    if resource.get(CONF_TYPE) != "module":
        updates[CONF_RESOURCE_TYPE_WS] = "module"
    if resource.get(CONF_URL) != resource_url:
        updates[CONF_URL] = resource_url
    if updates:
        await resources.async_update_item(resource[CONF_ID], updates)
        _LOGGER.info(
            "Updated My Station dashboard resource %s (%s)",
            resource[CONF_ID],
            resource_url,
        )

    if len(matches) > 1:
        _LOGGER.warning(
            "Found multiple My Station dashboard resources; kept all existing "
            "entries and updated %s",
            resource[CONF_ID],
        )


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up My Station from a config entry."""
    coordinator = MyStationDataUpdateCoordinator(hass, entry)
    await coordinator.async_config_entry_first_refresh()

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator
    entry.async_on_unload(entry.add_update_listener(_async_update_listener))

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a My Station config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        hass.data[DOMAIN].pop(entry.entry_id)
    return unload_ok


async def _async_update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload the entry after its options change."""
    await hass.config_entries.async_reload(entry.entry_id)
