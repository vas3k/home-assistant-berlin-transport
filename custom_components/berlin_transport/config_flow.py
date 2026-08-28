"""The Berlin (BVG) and Brandenburg (VBB) transport integration."""

from __future__ import annotations

import logging
from typing import Any, Optional

import aiohttp
import async_timeout
import homeassistant.helpers.config_validation as cv
import voluptuous as vol
from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.helpers import selector
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import (
    CONF_API_ENDPOINT,
    CONF_API_MAX_RESULTS,
    CONF_DEPARTURES_DIRECTION,
    CONF_DEPARTURES_DURATION,
    CONF_DEPARTURES_EXCLUDED_LINES,
    CONF_DEPARTURES_EXCLUDED_STOPS,
    CONF_DEPARTURES_NAME,
    CONF_DEPARTURES_STOP_ID,
    CONF_DEPARTURES_WALKING_TIME,
    CONF_FALLBACK_TIME,
    CONF_SELECTED_STOP,
    CONF_SHOW_API_LINE_COLORS,
    DEFAULT_API_ENDPOINT,
    DEFAULT_API_MAX_RESULTS,
    DEFAULT_FALLBACK_TIME,
    DOMAIN,  # noqa
    SUBENTRY_TYPE_STOP,
)
from .sensor import TRANSPORT_TYPES_SCHEMA

_LOGGER = logging.getLogger(__name__)

CONF_SEARCH = "search"
CONF_FOUND_STOPS = "found_stops"

# The hub holds the API endpoint and the settings shared by all its stops.
HUB_SCHEMA = vol.Schema(
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


async def get_stop_id(
    session: aiohttp.ClientSession,
    name,
    api_endpoint: str = DEFAULT_API_ENDPOINT,
    max_results: int = DEFAULT_API_MAX_RESULTS,
) -> Optional[list[dict[str, Any]]]:
    try:
        async with async_timeout.timeout(30):
            response = await session.get(
                url=f"{api_endpoint}/locations",
                params={
                    "query": name,
                    "results": max_results,
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
                    mode=selector.SelectSelectorMode.DROPDOWN,
                )
            )
        }
    )

    return schema


class TransportConfigFlowHandler(
    config_entries.ConfigFlow,
    domain=DOMAIN,
):  # pylint: disable=abstract-method
    """Create a hub entry that holds the API endpoint and shared settings.

    `is_matching` is left unimplemented on purpose: the hub is only ever set up
    by the user, never through discovery.
    """

    VERSION = 2

    CONNECTION_CLASS = config_entries.CONN_CLASS_CLOUD_POLL

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,  # pylint: disable=unused-argument
    ) -> OptionsFlowHandler:
        """Get the options flow for this handler."""
        return OptionsFlowHandler()

    @classmethod
    @callback
    def async_get_supported_subentry_types(
        cls,
        config_entry: config_entries.ConfigEntry,  # pylint: disable=unused-argument
    ) -> dict[str, type[config_entries.ConfigSubentryFlow]]:
        """Stops are added as subentries under the hub."""
        return {SUBENTRY_TYPE_STOP: StopSubentryFlowHandler}

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Create the hub."""
        if user_input is None:
            return self.async_show_form(
                step_id="user",
                data_schema=HUB_SCHEMA,
                errors={},
            )

        return self.async_create_entry(
            title=user_input[CONF_API_ENDPOINT],
            data={},
            options=user_input,
        )


class StopSubentryFlowHandler(config_entries.ConfigSubentryFlow):
    """Add or reconfigure a single stop under a hub entry."""

    def __init__(self) -> None:
        self.data: dict[str, Any] = {}

    def _hub_search_args(self) -> tuple[str, int]:
        """Endpoint and max results inherited from the parent hub entry."""
        entry = self._get_entry()
        return (
            entry.options.get(CONF_API_ENDPOINT) or DEFAULT_API_ENDPOINT,
            entry.options.get(CONF_API_MAX_RESULTS) or DEFAULT_API_MAX_RESULTS,
        )

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.SubentryFlowResult:
        """Search for a stop using the hub's API endpoint."""
        if user_input is None:
            return self.async_show_form(
                step_id="user",
                data_schema=NAME_SCHEMA,
                errors={},
            )

        api_endpoint, max_results = self._hub_search_args()
        session = async_get_clientsession(self.hass)
        self.data[CONF_FOUND_STOPS] = await get_stop_id(
            session, user_input[CONF_SEARCH], api_endpoint, max_results
        )
        return await self.async_step_stop()

    async def async_step_stop(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.SubentryFlowResult:
        """Select a stop from the search results."""
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
    ) -> config_entries.SubentryFlowResult:
        """Collect the per-stop details and create the subentry."""
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
    ) -> config_entries.SubentryFlowResult:
        """Reconfigure an existing stop's details (the stop itself is fixed)."""
        subentry = self._get_reconfigure_subentry()

        if user_input is not None:
            data = {**subentry.data, **user_input}
            return self.async_update_and_abort(
                self._get_entry(),
                subentry,
                data=data,
            )

        return self.async_show_form(
            step_id="reconfigure",
            data_schema=self.add_suggested_values_to_schema(
                DATA_SCHEMA, dict(subentry.data)
            ),
        )


class OptionsFlowHandler(
    config_entries.OptionsFlow
):  # pylint: disable=too-few-public-methods
    """Edit the hub-level (shared) settings for an existing entry."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Manage the options."""
        if user_input is not None:
            return self.async_create_entry(data=user_input)

        return self.async_show_form(
            step_id="init",
            data_schema=self.add_suggested_values_to_schema(
                HUB_SCHEMA,
                self.config_entry.options,
            ),
        )
