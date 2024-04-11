# mypy: disable-error-code="attr-defined,call-arg"
"""The Berlin (BVG) and Brandenburg (VBB) transport integration."""
from __future__ import annotations

import logging

from typing import Any, Optional
import requests
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.data_entry_flow import FlowResult
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers import selector

from .const import (
    API_ENDPOINT,
    API_MAX_RESULTS,
    CONF_DEPARTURES_STOP_ID,
    CONF_DEPARTURES_NAME,
    CONF_DEPARTURES_DIRECTION,
    CONF_DEPARTURES_EXCLUDED_STOPS,
    CONF_DEPARTURES_DURATION,
    CONF_DEPARTURES_WALKING_TIME,
    CONF_SHOW_API_LINE_COLORS,
    DOMAIN, # noqa
)

from .sensor import TRANSPORT_TYPES_SCHEMA

_LOGGER = logging.getLogger(__name__)

CONF_SEARCH = "search"
CONF_FOUND_STOPS = "found_stops"
CONF_SELECTED_STOP = "selected_stop"


DATA_SCHEMA = vol.Schema(
    {
        vol.Optional(CONF_DEPARTURES_DIRECTION): cv.string,
        vol.Optional(CONF_DEPARTURES_EXCLUDED_STOPS): cv.string,
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

# IPv6 is broken, see: https://github.com/public-transport/transport.rest/issues/20
requests.packages.urllib3.util.connection.HAS_IPV6 = False


def get_stop_id(name) -> Optional[list[dict[str, Any]]]:
    try:
        response = requests.get(
            url=f"{API_ENDPOINT}/locations",
            params={
                "query": name,
                "results": API_MAX_RESULTS,
            },
            timeout=30,
        )
        response.raise_for_status()
    except requests.exceptions.HTTPError as ex:
        _LOGGER.warning(f"API error: {ex}")
        return []
    except requests.exceptions.Timeout as ex:
        _LOGGER.warning(f"API timeout: {ex}")
        return []

    _LOGGER.debug(f"OK: stops for {name}: {response.text}")

    # parse JSON response
    try:
        stops = response.json()
    except requests.exceptions.InvalidJSONError as ex:
        _LOGGER.error(f"API invalid JSON: {ex}")
        return []

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
            vol.Required(CONF_SELECTED_STOP, default=False): selector.SelectSelector(
                selector.SelectSelectorConfig(
                    options=[
                        f"{stop[CONF_DEPARTURES_NAME]} [{stop[CONF_DEPARTURES_STOP_ID]}]"
                        for stop in stops
                    ],
                    mode=selector.SelectSelectorMode.DROPDOWN,
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
        self.data[CONF_FOUND_STOPS] = await self.hass.async_add_executor_job(
            get_stop_id, user_input[CONF_SEARCH]
        )

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
