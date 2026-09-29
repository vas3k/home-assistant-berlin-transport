"""The Berlin (BVG) and Brandenburg (VBB) transport integration."""

import asyncio
import copy
import logging
from collections.abc import Awaitable, Callable, Mapping
from typing import Any, Self

import homeassistant.helpers.config_validation as cv
import voluptuous as vol
from homeassistant import config_entries
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import selector

from .api import TransportApi, async_create_api
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
    CONF_STOP_NAMES,
    CONFIG_ENTRY_VERSION,
    DEFAULT_API_ENDPOINT,
    DEFAULT_API_MAX_RESULTS,
    DEFAULT_FALLBACK_TIME,
    DOMAIN,
    SUBENTRY_TYPE_STOP,
)
from .sensor import TRANSPORT_TYPES_SCHEMA

_LOGGER = logging.getLogger(__name__)

CONF_SEARCH = "search"
CONF_FOUND_STOPS = "found_stops"
CONF_SELECTED_STOPS = "selected_stops"

# Stop list options that get a page of their own, where stops are searched by
# name instead of typed in by id.
STOP_LIST_OPTIONS = (CONF_DEPARTURES_DIRECTION, CONF_DEPARTURES_EXCLUDED_STOPS)

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


def details_schema(line_names: list[str]) -> vol.Schema:
    """The remaining per-stop settings.

    `line_names` are offered as lines to exclude. Any other line name can still
    be typed in, e.g. one the API does not list for the stop.
    """
    return vol.Schema(
        {
            vol.Optional(
                CONF_DEPARTURES_EXCLUDED_LINES,
                default=list,
            ): selector.SelectSelector(
                selector.SelectSelectorConfig(
                    options=line_names,
                    multiple=True,
                    custom_value=True,
                    mode=selector.SelectSelectorMode.DROPDOWN,
                )
            ),
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
    api: TransportApi,
    name: str,
    max_results: int = DEFAULT_API_MAX_RESULTS,
) -> list[dict[str, Any]] | None:
    """The stops matching `name`, or None if the API fails."""
    stops = await api.locations(name, max_results)
    if stops is None:
        return None

    _LOGGER.debug(f"Stops for {name}: {stops}")

    # convert api data into objects
    return [
        {CONF_DEPARTURES_NAME: stop["name"], CONF_DEPARTURES_STOP_ID: stop["id"]}
        for stop in stops
        if stop.get("type") == "stop"
    ]


async def get_stop_name(api: TransportApi, stop_id: str) -> str | None:
    """The name of a stop, or None if the API does not know it or fails."""
    stop = await api.stop(stop_id, {})
    name: str | None = stop.get("name") if stop else None
    return name


async def get_line_names(api: TransportApi, stop_id: str) -> list[str]:
    """The names of the lines serving a stop, or none if the API fails.

    A name can be listed more than once, e.g. for a tram line and the bus
    replacing it, but is only returned once.
    """
    stop = await api.stop(stop_id, {"linesOfStops": "true"}) or {}
    return list(
        dict.fromkeys(
            line["name"] for line in stop.get("lines", []) if line.get("name")
        )
    )


def stop_label(stop: Mapping[str, Any]) -> str:
    """The `Name [id]` label a stop is shown as in the drop-down."""
    return f"{stop[CONF_DEPARTURES_NAME]} [{stop[CONF_DEPARTURES_STOP_ID]}]"


def list_stops(stops: list[dict[str, Any]]) -> vol.Schema:
    """Provides a drop down list of stops"""
    schema = vol.Schema(
        {
            vol.Required(CONF_SELECTED_STOP): selector.SelectSelector(
                selector.SelectSelectorConfig(
                    options=[stop_label(stop) for stop in stops],
                    mode=selector.SelectSelectorMode.DROPDOWN,
                )
            )
        }
    )

    return schema


def stop_option(stop_id: str, names: Mapping[str, str]) -> selector.SelectOptionDict:
    """A stop id as a select option, labelled with its name when known."""
    label = stop_id
    if stop_id in names:
        label = stop_label(
            {CONF_DEPARTURES_NAME: names[stop_id], CONF_DEPARTURES_STOP_ID: stop_id}
        )
    return selector.SelectOptionDict(value=stop_id, label=label)


def stop_list_schema(
    key: str, stop_ids: list[str], names: Mapping[str, str]
) -> vol.Schema:
    """The stops chosen for a stop list option.

    The chosen stops show as chips that can be removed. A stop id can also be
    typed in directly, e.g. when the search does not find it.
    """
    return vol.Schema(
        {
            vol.Optional(key, default=list): selector.SelectSelector(
                selector.SelectSelectorConfig(
                    options=[stop_option(stop_id, names) for stop_id in stop_ids],
                    multiple=True,
                    custom_value=True,
                    mode=selector.SelectSelectorMode.DROPDOWN,
                )
            ),
            vol.Optional(CONF_SEARCH): selector.TextSelector(),
        }
    )


def found_stops_schema(stops: list[dict[str, Any]]) -> vol.Schema:
    """Tick boxes for the stops found by a search."""
    return vol.Schema(
        {
            vol.Optional(CONF_SELECTED_STOPS, default=list): selector.SelectSelector(
                selector.SelectSelectorConfig(
                    options=[
                        selector.SelectOptionDict(
                            value=stop[CONF_DEPARTURES_STOP_ID], label=stop_label(stop)
                        )
                        for stop in stops
                    ],
                    multiple=True,
                    mode=selector.SelectSelectorMode.LIST,
                )
            )
        }
    )


def normalize_endpoint(endpoint: str) -> str:
    """The endpoint without surrounding whitespace or trailing slashes."""
    return endpoint.strip().rstrip("/")


def endpoint_in_use(
    hass: HomeAssistant, endpoint: str, exclude_entry_id: str | None = None
) -> bool:
    """Whether a hub other than `exclude_entry_id` already uses `endpoint`."""
    return any(
        normalize_endpoint(entry.options.get(CONF_API_ENDPOINT) or DEFAULT_API_ENDPOINT)
        == endpoint
        for entry in hass.config_entries.async_entries(DOMAIN)
        if entry.entry_id != exclude_entry_id
    )


async def async_endpoint_reachable(hass: HomeAssistant, endpoint: str) -> bool:
    """Whether `endpoint` answers a stop search with a list of locations."""
    api = await async_create_api(hass, endpoint)
    return isinstance(await api.locations("Berlin", 1), list)


class TransportConfigFlowHandler(config_entries.ConfigFlow, domain=DOMAIN):
    """Create a hub entry that holds the API endpoint and shared settings."""

    VERSION = CONFIG_ENTRY_VERSION

    CONNECTION_CLASS = config_entries.CONN_CLASS_CLOUD_POLL

    def is_matching(self, other_flow: Self) -> bool:
        """Never matches: the hub is only ever set up by the user, not discovered."""
        return False

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> "OptionsFlowHandler":
        """Get the options flow for this handler."""
        return OptionsFlowHandler()

    @classmethod
    @callback
    def async_get_supported_subentry_types(
        cls,
        config_entry: config_entries.ConfigEntry,
    ) -> dict[str, type[config_entries.ConfigSubentryFlow]]:
        """Stops are added as subentries under the hub."""
        return {SUBENTRY_TYPE_STOP: StopSubentryFlowHandler}

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Create the hub, one per API endpoint."""
        errors: dict[str, str] = {}
        if user_input is not None:
            endpoint = normalize_endpoint(user_input[CONF_API_ENDPOINT])
            if endpoint_in_use(self.hass, endpoint):
                errors[CONF_API_ENDPOINT] = "endpoint_in_use"
            elif not await async_endpoint_reachable(self.hass, endpoint):
                errors["base"] = "cannot_connect"
            else:
                return self.async_create_entry(
                    title=endpoint,
                    data={},
                    options={**user_input, CONF_API_ENDPOINT: endpoint},
                )

        return self.async_show_form(
            step_id="user",
            data_schema=self.add_suggested_values_to_schema(HUB_SCHEMA, user_input),
            errors=errors,
        )


class StopSubentryFlowHandler(config_entries.ConfigSubentryFlow):
    """Add or reconfigure a single stop under a hub entry."""

    def __init__(self) -> None:
        self.data: dict[str, Any] = {key: [] for key in STOP_LIST_OPTIONS}
        self.data[CONF_STOP_NAMES] = {}
        # Stop ids whose name was already looked up in this flow
        self._name_lookups: set[str] = set()

    def _hub_search_args(self) -> tuple[str, int]:
        """Endpoint and max results inherited from the parent hub entry."""
        entry = self._get_entry()
        return (
            entry.options.get(CONF_API_ENDPOINT) or DEFAULT_API_ENDPOINT,
            entry.options.get(CONF_API_MAX_RESULTS) or DEFAULT_API_MAX_RESULTS,
        )

    async def _async_api(self) -> TransportApi:
        """A client for the hub's API endpoint."""
        api_endpoint, _ = self._hub_search_args()
        # Build a client here instead of taking the hub's runtime_data since a
        # stop can still be added or reconfigured while the hub is not loaded
        # (for example when it was explicitly disabled)
        return await async_create_api(self.hass, api_endpoint)

    async def _async_search_stops(self, query: str) -> list[dict[str, Any]] | None:
        """Search stops by name using the hub's API endpoint.

        Returns None if the API fails, so that is not mistaken for no matches.
        """
        _, max_results = self._hub_search_args()
        return await get_stop_id(await self._async_api(), query, max_results)

    async def _async_resolve_stop_names(self, stop_ids: list[str]) -> None:
        """Look up the names of the stops that have none yet.

        Each stop is only looked up once per flow, so an unreachable API or an
        unknown stop id does not hold up every page it is shown on. Stops whose
        name is not found keep showing as the bare id.
        """
        names = self.data[CONF_STOP_NAMES]
        missing = [
            stop_id
            for stop_id in dict.fromkeys(stop_ids)
            if stop_id not in names and stop_id not in self._name_lookups
        ]
        if not missing:
            return

        self._name_lookups.update(missing)
        api = await self._async_api()
        found = await asyncio.gather(
            *(get_stop_name(api, stop_id) for stop_id in missing)
        )
        names.update(
            {
                stop_id: name
                for stop_id, name in zip(missing, found, strict=True)
                if name
            }
        )

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.SubentryFlowResult:
        """Search for a stop using the hub's API endpoint."""
        errors: dict[str, str] = {}
        if user_input is not None:
            found = await self._async_search_stops(user_input[CONF_SEARCH])
            if found is None:
                errors["base"] = "cannot_connect"
            elif not found:
                errors[CONF_SEARCH] = "no_stops_found"
            else:
                self.data[CONF_FOUND_STOPS] = found
                return await self.async_step_stop()

        return self.async_show_form(
            step_id="user",
            data_schema=self.add_suggested_values_to_schema(NAME_SCHEMA, user_input),
            errors=errors,
        )

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
            if user_input[CONF_SELECTED_STOP] == stop_label(stop)
        )
        (
            self.data[CONF_DEPARTURES_NAME],
            self.data[CONF_DEPARTURES_STOP_ID],
        ) = selected_stop
        _LOGGER.debug(f"OK: selected stop {selected_stop[0]} [{selected_stop[1]}]")

        return await self.async_step_direction()

    async def _async_step_stop_list(
        self,
        key: str,
        user_input: dict[str, Any] | None,
        results_step: Callable[[], Awaitable[config_entries.SubentryFlowResult]],
        next_step: Callable[[], Awaitable[config_entries.SubentryFlowResult]],
    ) -> config_entries.SubentryFlowResult:
        """Show the stops chosen for `key`, with a search to add more.

        Submitting a search goes to `results_step`, which comes back here.
        Submitting newly typed stop ids comes back here too, to show them with
        their names. Submitting without adding anything moves on to `next_step`.
        """
        errors: dict[str, str] = {}
        suggested_values: dict[str, Any] = {}
        if user_input is not None:
            typed = [i for i in user_input[key] if i not in self.data[key]]
            self.data[key] = user_input[key]
            query = user_input.get(CONF_SEARCH, "").strip()
            if query:
                found = await self._async_search_stops(query)
                if found is None:
                    errors["base"] = "cannot_connect"
                elif not found:
                    errors[CONF_SEARCH] = "no_stops_found"
                else:
                    self.data[CONF_FOUND_STOPS] = found
                    return await results_step()
                suggested_values[CONF_SEARCH] = query
            elif not typed:
                return await next_step()

        await self._async_resolve_stop_names(self.data[key])
        return self.async_show_form(
            step_id=key,
            data_schema=self.add_suggested_values_to_schema(
                stop_list_schema(key, self.data[key], self.data[CONF_STOP_NAMES]),
                {key: self.data[key], **suggested_values},
            ),
            errors=errors,
        )

    async def _async_step_found_stops(
        self,
        key: str,
        user_input: dict[str, Any] | None,
        list_step: Callable[[], Awaitable[config_entries.SubentryFlowResult]],
    ) -> config_entries.SubentryFlowResult:
        """Pick which of the found stops to add to `key`, then go back to it."""
        found = self.data[CONF_FOUND_STOPS]
        if user_input is None:
            return self.async_show_form(
                step_id=f"{key}_results",
                data_schema=found_stops_schema(found),
            )

        selected = user_input[CONF_SELECTED_STOPS]
        chosen = self.data[key]
        self.data[key] = [*chosen, *(i for i in selected if i not in chosen)]
        self.data[CONF_STOP_NAMES].update(
            {
                stop[CONF_DEPARTURES_STOP_ID]: stop[CONF_DEPARTURES_NAME]
                for stop in found
                if stop[CONF_DEPARTURES_STOP_ID] in selected
            }
        )
        return await list_step()

    async def async_step_direction(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.SubentryFlowResult:
        """Choose the stops that departures have to pass or end at."""
        return await self._async_step_stop_list(
            CONF_DEPARTURES_DIRECTION,
            user_input,
            self.async_step_direction_results,
            self.async_step_excluded_stops,
        )

    async def async_step_direction_results(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.SubentryFlowResult:
        """Pick the found stops to add to the direction filter."""
        return await self._async_step_found_stops(
            CONF_DEPARTURES_DIRECTION, user_input, self.async_step_direction
        )

    async def async_step_excluded_stops(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.SubentryFlowResult:
        """Choose the nearby stops whose departures to drop."""
        return await self._async_step_stop_list(
            CONF_DEPARTURES_EXCLUDED_STOPS,
            user_input,
            self.async_step_excluded_stops_results,
            self.async_step_details,
        )

    async def async_step_excluded_stops_results(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.SubentryFlowResult:
        """Pick the found stops to add to the ignored stops."""
        return await self._async_step_found_stops(
            CONF_DEPARTURES_EXCLUDED_STOPS, user_input, self.async_step_excluded_stops
        )

    def _stop_list_data(self) -> dict[str, Any]:
        """The chosen stop lists, with the names of just the stops in them."""
        lists = {key: self.data[key] for key in STOP_LIST_OPTIONS}
        chosen = {stop_id for stop_ids in lists.values() for stop_id in stop_ids}
        names = {
            stop_id: name
            for stop_id, name in self.data[CONF_STOP_NAMES].items()
            if stop_id in chosen
        }
        return {**lists, CONF_STOP_NAMES: names}

    async def async_step_details(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.SubentryFlowResult:
        """Collect the remaining per-stop settings and save the stop."""
        reconfiguring = self.source == config_entries.SOURCE_RECONFIGURE
        if user_input is None:
            current: Mapping[str, Any] = {}
            if reconfiguring:
                current = self._get_reconfigure_subentry().data
            line_names = await get_line_names(
                await self._async_api(), self.data[CONF_DEPARTURES_STOP_ID]
            )
            # Keep offering the lines already excluded, even if the API no
            # longer lists them (or could not be reached).
            line_names = list(
                dict.fromkeys(
                    [*line_names, *current.get(CONF_DEPARTURES_EXCLUDED_LINES, [])]
                )
            )
            return self.async_show_form(
                step_id="details",
                data_schema=self.add_suggested_values_to_schema(
                    details_schema(line_names), current
                ),
                errors={},
            )

        data = {**user_input, **self._stop_list_data()}
        if reconfiguring:
            subentry = self._get_reconfigure_subentry()
            return self.async_update_and_abort(
                self._get_entry(),
                subentry,
                data={**subentry.data, **data},
            )

        data[CONF_DEPARTURES_STOP_ID] = self.data[CONF_DEPARTURES_STOP_ID]
        data[CONF_DEPARTURES_NAME] = self.data[CONF_DEPARTURES_NAME]
        return self.async_create_entry(
            title=f"{data[CONF_DEPARTURES_NAME]} [{data[CONF_DEPARTURES_STOP_ID]}]",
            data=data,
        )

    async def async_step_reconfigure(
        self,
        user_input: dict[str, Any] | None = None,  # pylint: disable=unused-argument
    ) -> config_entries.SubentryFlowResult:
        """Reconfigure an existing stop (the stop itself is fixed).

        Goes through the same pages as adding a stop does after picking it.
        """
        subentry = self._get_reconfigure_subentry()
        # Work on a copy: the stored data is only read-only at the top level
        # (it's a MappingProxyType), so editing its lists or names in place
        # would edit the stored stop (and the running sensor's filters) without
        # saving. Updating keeps the defaults for keys the stop was saved
        # without, like the names of older stops.
        self.data.update(copy.deepcopy(dict(subentry.data)))
        return await self.async_step_direction()


class OptionsFlowHandler(config_entries.OptionsFlow):
    """Edit the hub-level (shared) settings for an existing entry."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Manage the options.

        A new endpoint is only accepted if no other hub uses it and it can be
        reached. The hub's title follows the endpoint, unless it was renamed.
        """
        entry = self.config_entry
        errors: dict[str, str] = {}
        if user_input is not None:
            old_endpoint = normalize_endpoint(
                entry.options.get(CONF_API_ENDPOINT) or DEFAULT_API_ENDPOINT
            )
            endpoint = normalize_endpoint(user_input[CONF_API_ENDPOINT])
            if endpoint != old_endpoint:
                if endpoint_in_use(self.hass, endpoint, entry.entry_id):
                    errors[CONF_API_ENDPOINT] = "endpoint_in_use"
                elif not await async_endpoint_reachable(self.hass, endpoint):
                    errors["base"] = "cannot_connect"

            if not errors:
                options = {**user_input, CONF_API_ENDPOINT: endpoint}
                if normalize_endpoint(entry.title) == old_endpoint:
                    # Update the title together with the options, so the hub
                    # is reloaded once and not once for each change.
                    self.hass.config_entries.async_update_entry(
                        entry, title=endpoint, options=options
                    )
                return self.async_create_entry(data=options)

        return self.async_show_form(
            step_id="init",
            data_schema=self.add_suggested_values_to_schema(
                HUB_SCHEMA,
                user_input or entry.options,
            ),
            errors=errors,
        )
