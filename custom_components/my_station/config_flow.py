"""Config flow for My Station."""

from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_NAME
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.selector import (
    TextSelector,
    TextSelectorConfig,
    TextSelectorType,
)

from .api import (
    RejseplanenApiClient,
    RejseplanenAuthenticationError,
    RejseplanenConnectionError,
)
from .const import (
    CONF_ACCESS_ID,
    CONF_DURATION,
    CONF_MAX_JOURNEYS,
    CONF_STOP_ID,
    CONF_UPDATE_INTERVAL,
    DEFAULT_DURATION,
    DEFAULT_MAX_JOURNEYS,
    DEFAULT_NAME,
    DEFAULT_STOP_ID,
    DEFAULT_UPDATE_INTERVAL,
    DOMAIN,
    MAX_DURATION,
    MAX_MAX_JOURNEYS,
    MAX_UPDATE_INTERVAL,
    MIN_DURATION,
    MIN_MAX_JOURNEYS,
    MIN_UPDATE_INTERVAL,
)

_LOGGER = logging.getLogger(__name__)


def _normalize_required_text(
    data: dict[str, Any], key: str, errors: dict[str, str]
) -> bool:
    """Normalize a required text field after frontend schema validation."""
    value = data.get(key)
    if not isinstance(value, str) or not value.strip():
        errors[key] = "required"
        return False
    data[key] = value.strip()
    return True


def _number_value(minimum: int, maximum: int) -> vol.All:
    """Build a bounded integer validator."""
    return vol.All(vol.Coerce(int), vol.Range(min=minimum, max=maximum))


def _user_schema(defaults: dict[str, Any] | None = None) -> vol.Schema:
    """Return the schema for initial setup."""
    defaults = defaults or {}
    return vol.Schema(
        {
            vol.Required(
                CONF_NAME, default=defaults.get(CONF_NAME, DEFAULT_NAME)
            ): TextSelector(),
            vol.Required(CONF_ACCESS_ID): TextSelector(
                TextSelectorConfig(type=TextSelectorType.PASSWORD)
            ),
            vol.Required(
                CONF_STOP_ID, default=defaults.get(CONF_STOP_ID, DEFAULT_STOP_ID)
            ): TextSelector(),
            vol.Required(
                CONF_MAX_JOURNEYS,
                default=defaults.get(CONF_MAX_JOURNEYS, DEFAULT_MAX_JOURNEYS),
            ): _number_value(MIN_MAX_JOURNEYS, MAX_MAX_JOURNEYS),
            vol.Required(
                CONF_DURATION,
                default=defaults.get(CONF_DURATION, DEFAULT_DURATION),
            ): _number_value(MIN_DURATION, MAX_DURATION),
            vol.Required(
                CONF_UPDATE_INTERVAL,
                default=defaults.get(
                    CONF_UPDATE_INTERVAL, DEFAULT_UPDATE_INTERVAL
                ),
            ): _number_value(MIN_UPDATE_INTERVAL, MAX_UPDATE_INTERVAL),
        }
    )


def _options_schema(defaults: dict[str, Any]) -> vol.Schema:
    """Return the schema for runtime-tunable options."""
    return vol.Schema(
        {
            vol.Required(
                CONF_MAX_JOURNEYS,
                default=defaults.get(CONF_MAX_JOURNEYS, DEFAULT_MAX_JOURNEYS),
            ): _number_value(MIN_MAX_JOURNEYS, MAX_MAX_JOURNEYS),
            vol.Required(
                CONF_DURATION,
                default=defaults.get(CONF_DURATION, DEFAULT_DURATION),
            ): _number_value(MIN_DURATION, MAX_DURATION),
            vol.Required(
                CONF_UPDATE_INTERVAL,
                default=defaults.get(
                    CONF_UPDATE_INTERVAL, DEFAULT_UPDATE_INTERVAL
                ),
            ): _number_value(MIN_UPDATE_INTERVAL, MAX_UPDATE_INTERVAL),
        }
    )


def _reconfigure_schema(stop_id: str) -> vol.Schema:
    """Return the schema for editable connection settings."""
    return vol.Schema(
        {
            vol.Optional(CONF_ACCESS_ID): TextSelector(
                TextSelectorConfig(type=TextSelectorType.PASSWORD)
            ),
            vol.Required(CONF_STOP_ID, default=stop_id): TextSelector(),
        }
    )


async def _async_validate_input(hass: HomeAssistant, data: dict[str, Any]) -> None:
    """Verify credentials and station settings against Rejseplanen."""
    client = RejseplanenApiClient(async_get_clientsession(hass))
    await client.async_get_departures(
        access_id=data[CONF_ACCESS_ID],
        stop_id=data[CONF_STOP_ID],
        max_journeys=data[CONF_MAX_JOURNEYS],
        duration=data[CONF_DURATION],
    )


class MyStationConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for My Station."""

    VERSION = 1
    _reauth_entry: config_entries.ConfigEntry | None = None

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ):
        """Handle initial setup."""
        errors: dict[str, str] = {}

        if user_input is not None:
            fields_valid = True
            for key in (CONF_NAME, CONF_ACCESS_ID, CONF_STOP_ID):
                if not _normalize_required_text(user_input, key, errors):
                    fields_valid = False
            if fields_valid:
                try:
                    await _async_validate_input(self.hass, user_input)
                except RejseplanenAuthenticationError:
                    errors["base"] = "invalid_auth"
                except RejseplanenConnectionError:
                    errors["base"] = "cannot_connect"
                except Exception:  # noqa: BLE001 - config flows must show a form
                    _LOGGER.exception("Unexpected exception validating My Station")
                    errors["base"] = "unknown"
                else:
                    await self.async_set_unique_id(user_input[CONF_STOP_ID])
                    self._abort_if_unique_id_configured()
                    return self.async_create_entry(
                        title=user_input[CONF_NAME], data=user_input
                    )

        return self.async_show_form(
            step_id="user",
            data_schema=_user_schema(user_input),
            errors=errors,
        )

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ):
        """Allow the API access ID and station ID to be changed."""
        entry = self.hass.config_entries.async_get_entry(self.context["entry_id"])
        assert entry is not None
        errors: dict[str, str] = {}

        if user_input is not None and _normalize_required_text(
            user_input, CONF_STOP_ID, errors
        ):
            updated_data = dict(entry.data)
            access_id = user_input.get(CONF_ACCESS_ID)
            if isinstance(access_id, str) and access_id.strip():
                updated_data[CONF_ACCESS_ID] = access_id.strip()
            updated_data[CONF_STOP_ID] = user_input[CONF_STOP_ID]

            duplicate = any(
                configured.entry_id != entry.entry_id
                and (
                    configured.unique_id == updated_data[CONF_STOP_ID]
                    or configured.data.get(CONF_STOP_ID)
                    == updated_data[CONF_STOP_ID]
                )
                for configured in self._async_current_entries()
            )
            if duplicate:
                errors["base"] = "already_configured"
            else:
                validation_data = {**updated_data, **entry.options}
                try:
                    await _async_validate_input(self.hass, validation_data)
                except RejseplanenAuthenticationError:
                    errors["base"] = "invalid_auth"
                except RejseplanenConnectionError:
                    errors["base"] = "cannot_connect"
                except Exception:  # noqa: BLE001 - config flows must show a form
                    _LOGGER.exception("Unexpected exception reconfiguring My Station")
                    errors["base"] = "unknown"
                else:
                    return self.async_update_reload_and_abort(
                        entry,
                        data=updated_data,
                        unique_id=updated_data[CONF_STOP_ID],
                        reason="reconfigure_successful",
                    )

        return self.async_show_form(
            step_id="reconfigure",
            data_schema=_reconfigure_schema(
                user_input.get(CONF_STOP_ID, entry.data[CONF_STOP_ID])
                if user_input is not None
                else entry.data[CONF_STOP_ID]
            ),
            errors=errors,
        )

    async def async_step_reauth(self, _entry_data: dict[str, Any]):
        """Start reauthentication."""
        self._reauth_entry = self.hass.config_entries.async_get_entry(
            self.context["entry_id"]
        )
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ):
        """Confirm a replacement access ID."""
        errors: dict[str, str] = {}
        entry = self._reauth_entry

        if user_input is not None and entry is not None:
            if _normalize_required_text(user_input, CONF_ACCESS_ID, errors):
                updated_data = {
                    **entry.data,
                    CONF_ACCESS_ID: user_input[CONF_ACCESS_ID],
                }
                try:
                    await _async_validate_input(self.hass, updated_data)
                except RejseplanenAuthenticationError:
                    errors["base"] = "invalid_auth"
                except RejseplanenConnectionError:
                    errors["base"] = "cannot_connect"
                except Exception:  # noqa: BLE001 - config flows must show a form
                    _LOGGER.exception(
                        "Unexpected exception reauthenticating My Station"
                    )
                    errors["base"] = "unknown"
                else:
                    return self.async_update_reload_and_abort(
                        entry,
                        data=updated_data,
                        reason="reauth_successful",
                    )

        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_ACCESS_ID): TextSelector(
                        TextSelectorConfig(type=TextSelectorType.PASSWORD)
                    )
                }
            ),
            errors=errors,
        )

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> config_entries.OptionsFlow:
        """Return the options flow handler."""
        return MyStationOptionsFlow(config_entry)


class MyStationOptionsFlow(config_entries.OptionsFlow):
    """Handle My Station options."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        """Initialize the options flow."""
        self._config_entry = config_entry

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ):
        """Manage polling and response-size options."""
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        current = {**self._config_entry.data, **self._config_entry.options}
        return self.async_show_form(
            step_id="init", data_schema=_options_schema(current)
        )
