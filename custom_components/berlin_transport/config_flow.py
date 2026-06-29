# mypy: disable-error-code="attr-defined,call-arg"
"""The Berlin (BVG) and Brandenburg (VBB) transport integration."""
from __future__ import annotations

import logging

from typing import Any, Optional
import aiohttp
import async_timeout
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers.aiohttp_client import async_get_clientsession
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers import selector

from .const import (
    CONF_API_ENDPOINT,
    CONF_API_MAX_RESULTS,
    CONF_FALLBACK_TIME,
    DEFAULT_API_ENDPOINT,
    DEFAULT_API_MAX_RESULTS,
    DEFAULT_FALLBACK_TIME,
    CONF_DEPARTURES_STOP_ID,
    CONF_DEPARTURES_NAME,
    CONF_SELECTED_STOP,
    CONF_DEPARTURES_DIRECTION,
    CONF_DEPARTURES_EXCLUDED_STOPS,
    CONF_DEPARTURES_EXCLUDED_LINES,
    CONF_DEPARTURES_DURATION,
    CONF_DEPARTURES_WALKING_TIME,
    CONF_SHOW_API_LINE_COLORS,
    DOMAIN, # noqa
)

from .sensor import TRANSPORT_TYPES_SCHEMA

_LOGGER = logging.getLogger(__name__)

CONF_SEARCH = "search"
CONF_FOUND_STOPS = "found_stops"

DATA_SCHEMA = vol.Schema(
    {
        vol.Optional(CONF_DEPARTURES_DIRECTION): cv.string,
        vol.Optional(CONF_DEPARTURES_EXCLUDED_STOPS): cv.string,
        vol.Optional(CONF_DEPARTURES_EXCLUDED_LINES): cv.string,
        vol.Optional(CONF_DEPARTURES_DURATION): cv.positive_int,
        vol.Optional(CONF_DEPARTURES_WALKING_TIME, default=1): cv.positive_int,
        vol.Optional(CONF_SHOW_API_LINE_COLORS, default=False): cv.boolean,
        **TRANSPORT_TYPES_SCHEMA,
    }
)

NAME_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_SEARCH): cv.string,
    }
)

OPTIONS_SCHEMA = vol.Schema(
    {
        vol.Optional(CONF_API_ENDPOINT, default=DEFAULT_API_ENDPOINT): cv.string,
        vol.Optional(
            CONF_API_MAX_RESULTS, default=DEFAULT_API_MAX_RESULTS
        ): cv.positive_int,
        vol.Optional(
            CONF_FALLBACK_TIME, default=DEFAULT_FALLBACK_TIME
        ): cv.positive_int,
    }
)


async def get_stop_id(session: aiohttp.ClientSession, name) -> Optional[list[dict[str, Any]]]:
    try:
        async with async_timeout.timeout(30):
            response = await session.get(
                url=f"{DEFAULT_API_ENDPOINT}/locations",
                params={
                    "query": name,
                    "results": DEFAULT_API_MAX_RESULTS,
                },
            )
            response.raise_for_status()
            stops = await response.json()
    except aiohttp.ClientError as ex:
        _LOGGER.warning(f"API error: {ex}")
        return []
    except Exception as ex:
        _LOGGER.error(f"Unexpected error: {ex}")
        return []

    _LOGGER.debug(f"OK: stops for {name}: {stops}")

    # convert api data into objects
    return [
        {CONF_DEPARTURES_NAME: stop["name"], CONF_DEPARTURES_STOP_ID: stop["id"]}
        for stop in stops
        if stop["type"] == "stop"
    ]


def list_stops(stops) -> Optional[vol.Schema]:
    """Provides a drop down list of stops"""
    schema = vol.Schema(
        {
            vol.Required(CONF_SELECTED_STOP): selector.SelectSelector(
                selector.SelectSelectorConfig(
                    options=[
                        f"{stop[CONF_DEPARTURES_NAME]} [{stop[CONF_DEPARTURES_STOP_ID]}]"
                        for stop in stops
                    ],
                    mode=selector.SelectSelectorMode.DROPDOWN
                )
            )
        }
    )

    return schema


class TransportConfigFlowHandler(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1

    CONNECTION_CLASS = config_entries.CONN_CLASS_CLOUD_POLL

    def __init__(self) -> None:
        """Init the ConfigFlow."""
        self.data: dict[str, Any] = {}

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,  # pylint: disable=unused-argument
    ) -> OptionsFlowHandler:
        """Get the options flow for this handler."""
        return OptionsFlowHandler()

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step."""
        if user_input is None:
            return self.async_show_form(
                step_id="user",
                data_schema=NAME_SCHEMA,
                errors={},
            )

        session = async_get_clientsession(self.hass)
        self.data[CONF_FOUND_STOPS] = await get_stop_id(session, user_input[CONF_SEARCH])

        _LOGGER.debug(
            f"OK: found stops for {user_input[CONF_SEARCH]}: {self.data[CONF_FOUND_STOPS]}"
        )

        return await self.async_step_stop()

    async def async_step_stop(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step."""
        if user_input is None:
            return self.async_show_form(
                step_id="stop",
                data_schema=list_stops(self.data[CONF_FOUND_STOPS]),
                errors={},
            )

        selected_stop = next(
            (stop[CONF_DEPARTURES_NAME], stop[CONF_DEPARTURES_STOP_ID])
            for stop in self.data[CONF_FOUND_STOPS]
            if user_input[CONF_SELECTED_STOP]
            == f"{stop[CONF_DEPARTURES_NAME]} [{stop[CONF_DEPARTURES_STOP_ID]}]"
        )
        (
            self.data[CONF_DEPARTURES_NAME],
            self.data[CONF_DEPARTURES_STOP_ID],
        ) = selected_stop
        _LOGGER.debug(f"OK: selected stop {selected_stop[0]} [{selected_stop[1]}]")

        return await self.async_step_details()

    async def async_step_details(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the details."""
        if user_input is None:
            return self.async_show_form(
                step_id="details",
                data_schema=DATA_SCHEMA,
                errors={},
            )

        data = user_input
        data[CONF_DEPARTURES_STOP_ID] = self.data[CONF_DEPARTURES_STOP_ID]
        data[CONF_DEPARTURES_NAME] = self.data[CONF_DEPARTURES_NAME]
        return self.async_create_entry(
            title=f"{data[CONF_DEPARTURES_NAME]} [{data[CONF_DEPARTURES_STOP_ID]}]",
            data=data,
        )

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle reconfiguration."""
        entry = self._get_reconfigure_entry()

        if user_input is not None:
            data = user_input
            data[CONF_DEPARTURES_STOP_ID] = entry.data[CONF_DEPARTURES_STOP_ID]
            data[CONF_DEPARTURES_NAME] = entry.data[CONF_DEPARTURES_NAME]
            return self.async_update_reload_and_abort(
                entry,
                data=data,
            )

        return self.async_show_form(
            step_id="reconfigure",
            data_schema=self.add_suggested_values_to_schema(
                DATA_SCHEMA, dict(entry.data)
            ),
        )


class OptionsFlowHandler(config_entries.OptionsFlow):  # pylint: disable=too-few-public-methods
    """Handle the options (advanced settings) for an existing entry."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Manage the options."""
        if user_input is not None:
            return self.async_create_entry(data=user_input)

        return self.async_show_form(
            step_id="init",
            data_schema=self.add_suggested_values_to_schema(
                OPTIONS_SCHEMA, self.config_entry.options
            ),
        )
