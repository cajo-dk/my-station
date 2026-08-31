"""Data update coordinator for My Station."""

from __future__ import annotations

from datetime import timedelta
import logging
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import (
    RejseplanenApiClient,
    RejseplanenAuthenticationError,
    RejseplanenConnectionError,
    build_payload,
    compact_departure_data,
)
from .const import (
    CATEGORY_FILTER,
    CONF_ACCESS_ID,
    CONF_DURATION,
    CONF_MAX_JOURNEYS,
    CONF_STOP_ID,
    CONF_UPDATE_INTERVAL,
    DEFAULT_DURATION,
    DEFAULT_MAX_JOURNEYS,
    DEFAULT_UPDATE_INTERVAL,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)


class MyStationDataUpdateCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Coordinate departure updates for one config entry."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        """Initialize the coordinator."""
        self.config = {**entry.data, **entry.options}
        self.api = RejseplanenApiClient(async_get_clientsession(hass))

        super().__init__(
            hass,
            _LOGGER,
            name=f"{DOMAIN}_{entry.entry_id}",
            update_interval=timedelta(
                minutes=self.config.get(
                    CONF_UPDATE_INTERVAL, DEFAULT_UPDATE_INTERVAL
                )
            ),
            always_update=False,
        )

    async def _async_update_data(self) -> dict[str, Any]:
        """Fetch and compact the latest departure board."""
        try:
            raw = await self.api.async_get_departures(
                access_id=self.config[CONF_ACCESS_ID],
                stop_id=self.config[CONF_STOP_ID],
                max_journeys=self.config.get(
                    CONF_MAX_JOURNEYS, DEFAULT_MAX_JOURNEYS
                ),
                duration=self.config.get(CONF_DURATION, DEFAULT_DURATION),
            )
        except RejseplanenAuthenticationError as err:
            raise ConfigEntryAuthFailed(
                "Rejseplanen rejected the configured access ID"
            ) from err
        except RejseplanenConnectionError as err:
            raise UpdateFailed(str(err)) from err

        return build_payload(compact_departure_data(raw, CATEGORY_FILTER))
