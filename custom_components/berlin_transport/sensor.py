# mypy: disable-error-code="attr-defined"

"""The Berlin (BVG) and Brandenburg (VBB) transport integration."""

from __future__ import annotations
import logging
from typing import Any, Mapping
from datetime import datetime, timedelta

import aiohttp
import async_timeout
import voluptuous as vol

from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType
from homeassistant.config_entries import ConfigEntry
from homeassistant.components.sensor import SensorEntity
from homeassistant.components.sensor import PLATFORM_SCHEMA

from .const import (  # pylint: disable=unused-import
    DOMAIN,  # noqa
    SCAN_INTERVAL,  # noqa
    API_ENDPOINT,
    API_MAX_RESULTS,
    FALLBACK_TIME,
    CONF_DEPARTURES,
    CONF_DEPARTURES_DIRECTION,
    CONF_DEPARTURES_EXCLUDED_STOPS,
    CONF_DEPARTURES_EXCLUDED_LINES,
    CONF_DEPARTURES_DURATION,
    CONF_DEPARTURES_STOP_ID,
    CONF_DEPARTURES_WALKING_TIME,
    CONF_SHOW_API_LINE_COLORS,
    CONF_TYPE_BUS,
    CONF_TYPE_EXPRESS,
    CONF_TYPE_FERRY,
    CONF_TYPE_REGIONAL,
    CONF_TYPE_SUBURBAN,
    CONF_TYPE_SUBWAY,
    CONF_TYPE_TRAM,
    CONF_DEPARTURES_NAME,
    DEFAULT_ICON,
)
from .departure import Departure

_LOGGER = logging.getLogger(__name__)

TRANSPORT_TYPES_SCHEMA = {
    vol.Optional(CONF_TYPE_SUBURBAN, default=True): cv.boolean,
    vol.Optional(CONF_TYPE_SUBWAY, default=True): cv.boolean,
    vol.Optional(CONF_TYPE_TRAM, default=True): cv.boolean,
    vol.Optional(CONF_TYPE_BUS, default=True): cv.boolean,
    vol.Optional(CONF_TYPE_FERRY, default=True): cv.boolean,
    vol.Optional(CONF_TYPE_EXPRESS, default=True): cv.boolean,
    vol.Optional(CONF_TYPE_REGIONAL, default=True): cv.boolean,
}

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Optional(CONF_DEPARTURES): [
            {
                vol.Required(CONF_DEPARTURES_NAME): cv.string,
                vol.Required(CONF_DEPARTURES_STOP_ID): cv.positive_int,
                vol.Optional(CONF_DEPARTURES_DIRECTION): cv.string,
                vol.Optional(CONF_DEPARTURES_EXCLUDED_STOPS): cv.string,
                vol.Optional(CONF_DEPARTURES_EXCLUDED_LINES): cv.string,
                vol.Optional(CONF_DEPARTURES_DURATION): cv.positive_int,
                vol.Optional(CONF_DEPARTURES_WALKING_TIME, default=1): cv.positive_int,
                vol.Optional(CONF_SHOW_API_LINE_COLORS, default=False): cv.boolean,
                **TRANSPORT_TYPES_SCHEMA,
            }
        ]
    }
)


async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    async_add_entities: AddEntitiesCallback,
    _: DiscoveryInfoType | None = None,
) -> None:
    """Set up the sensor platform."""
    if CONF_DEPARTURES in config:
        for departure in config[CONF_DEPARTURES]:
            async_add_entities([TransportSensor(hass, departure)], True)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    async_add_entities([TransportSensor(hass, config_entry.data, config_entry.entry_id)], True)


class TransportSensor(SensorEntity):
    departures: list[Departure] = []

    def __init__(
        self,
        hass: HomeAssistant,
        config: Mapping[str, Any],
        entry_id: str | None = None
    ) -> None:
        self.hass: HomeAssistant = hass
        self.config = config
        self._entry_id = entry_id
        self.stop_id: int = config[CONF_DEPARTURES_STOP_ID]
        self.excluded_stops: str | None = config.get(CONF_DEPARTURES_EXCLUDED_STOPS)
        self.excluded_lines: str | None = config.get(CONF_DEPARTURES_EXCLUDED_LINES)
        self.sensor_name: str | None = config.get(CONF_DEPARTURES_NAME)
        self.direction: str | None = config.get(CONF_DEPARTURES_DIRECTION)
        self.duration: int | None = config.get(CONF_DEPARTURES_DURATION)
        self.walking_time: int = config.get(CONF_DEPARTURES_WALKING_TIME) or 1
        # we add +1 minute anyway to delete the "just gone" transport
        self.show_api_line_colors: bool = config.get(CONF_SHOW_API_LINE_COLORS) or False
        self.session = async_get_clientsession(hass)
        self.last_update_success: datetime | None = None
        self._attr_available: bool = True

    @property
    def name(self) -> str:
        return self.sensor_name or f"Stop ID: {self.stop_id}"

    @property
    def icon(self) -> str:
        next_departure = self.next_departure()
        if next_departure:
            return next_departure.icon
        return DEFAULT_ICON

    @property
    def unique_id(self) -> str:
        return self._entry_id or f"stop_{self.stop_id}_{self.sensor_name}_departures"

    @property
    def native_value(self) -> str:
        next_departure = self.next_departure()
        if next_departure:
            return f"Next {next_departure.line_name} at {next_departure.time}"
        return "N/A"

    @property
    def extra_state_attributes(self):
        return {
            "departures": [
                departure.to_dict(self.show_api_line_colors, self.walking_time)
                for departure in self.departures or []
            ]
        }

    async def async_update(self):
        departures = await self.fetch_departures()
        now_utc = datetime.utcnow()
        if departures is None:
            if (
                self.departures and
                self.last_update_success and
                (now_utc - self.last_update_success) <= FALLBACK_TIME
            ):
                self.departures = [
                    d for d in self.departures
                    if d.timestamp >= datetime.now(d.timestamp.tzinfo)
                ]
                if not self.departures:
                    self._attr_available = False
            else:
                self._attr_available = False
                self.departures = []
        else:
            self._attr_available = True
            self.departures = departures
            self.last_update_success = now_utc

    async def fetch_directional_departure(self, direction: str | None) -> list[Departure] | None:
        try:
            params: dict[str, Any] = {
                "when": (datetime.utcnow() + timedelta(minutes=self.walking_time)).isoformat(),
                "results": API_MAX_RESULTS,
                "suburban": str(self.config.get(CONF_TYPE_SUBURBAN) or False).lower(),
                "subway": str(self.config.get(CONF_TYPE_SUBWAY) or False).lower(),
                "tram": str(self.config.get(CONF_TYPE_TRAM) or False).lower(),
                "bus": str(self.config.get(CONF_TYPE_BUS) or False).lower(),
                "ferry": str(self.config.get(CONF_TYPE_FERRY) or False).lower(),
                "express": str(self.config.get(CONF_TYPE_EXPRESS) or False).lower(),
                "regional": str(self.config.get(CONF_TYPE_REGIONAL) or False).lower(),
            }
            if self.duration is not None:
                params["duration"] = self.duration
            if direction is not None:
                params["direction"] = direction

            async with async_timeout.timeout(30):
                response = await self.session.get(
                    url=f"{API_ENDPOINT}/stops/{self.stop_id}/departures",
                    params=params,
                )
                response.raise_for_status()
                departures = await response.json()
        except aiohttp.ClientError as ex:
            _LOGGER.warning(f"API error: {ex}")
            return None
        except Exception as ex:
            _LOGGER.error(f"Unexpected error: {ex}")
            return None

        if not departures or "departures" not in departures:
            _LOGGER.warning(f"No departures found for {self.stop_id}")
            return []

        if self.excluded_stops is None:
            excluded_stops = []
        else:
            excluded_stops = self.excluded_stops.split(",")

        if self.excluded_lines is None:
            excluded_lines = []
        else:
            excluded_lines = self.excluded_lines.split(",")

        # convert api data into objects
        return [
            Departure.from_dict(departure)
            for departure in (departures.get("departures") or [])
            if departure.get("stop", {}).get("id") not in excluded_stops
            and departure.get("line", {}).get("name") not in excluded_lines
        ]

    async def fetch_departures(self) -> list[Departure] | None:
        departures = []

        if self.direction is None:
            res = await self.fetch_directional_departure(self.direction)
            if res is None:
                return None
            departures += res
        else:
            for direction in self.direction.split(","):
                res = await self.fetch_directional_departure(direction)
                if res is None:
                    return None
                departures += res

        # Get rid of duplicates
        # Duplicates should only exist for the Ringbahn and filtering for both
        # directions
        deduplicated_departures = set(departures)

        return sorted(deduplicated_departures, key=lambda d: d.timestamp)

    def next_departure(self):
        if self.departures and isinstance(self.departures, list):
            return self.departures[0]
        return None
