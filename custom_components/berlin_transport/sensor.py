# mypy: disable-error-code="attr-defined"

"""The Berlin (BVG) and Brandenburg (VBB) transport integration."""
from __future__ import annotations
import logging
from datetime import datetime, timedelta

from requests.exceptions import HTTPError, InvalidJSONError, Timeout
from requests_cache import CachedSession
import voluptuous as vol

from homeassistant.core import HomeAssistant
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
    CONF_DEPARTURES,
    CONF_DEPARTURES_DIRECTION,
    CONF_DEPARTURES_EXCLUDED_STOPS,
    CONF_DEPARTURES_DURATION,
    CONF_DEPARTURES_STOP_ID,
    CONF_DEPARTURES_WALKING_TIME,
    CONF_EXCLUDE_RINGBAHN_CLOCKWISE,
    CONF_EXCLUDE_RINGBAHN_COUNTERCLOCKWISE,
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
                vol.Optional(CONF_DEPARTURES_DURATION): cv.positive_int,
                vol.Optional(CONF_DEPARTURES_WALKING_TIME, default=1): cv.positive_int,
                vol.Optional(CONF_SHOW_API_LINE_COLORS, default=False): cv.boolean,
                vol.Optional(CONF_EXCLUDE_RINGBAHN_CLOCKWISE, default=False): cv.boolean,
                vol.Optional(CONF_EXCLUDE_RINGBAHN_COUNTERCLOCKWISE, default=False): cv.boolean,
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
            async_add_entities([TransportSensor(hass, departure)])


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    async_add_entities([TransportSensor(hass, config_entry.data)])


class TransportSensor(SensorEntity):
    departures: list[Departure] = []

    def __init__(self, hass: HomeAssistant, config: dict) -> None:
        self.hass: HomeAssistant = hass
        self.config: dict = config
        self.stop_id: int = config[CONF_DEPARTURES_STOP_ID]
        self.excluded_stops: str | None = config.get(CONF_DEPARTURES_EXCLUDED_STOPS)
        self.sensor_name: str | None = config.get(CONF_DEPARTURES_NAME)
        self.direction: str | None = config.get(CONF_DEPARTURES_DIRECTION)
        self.duration: int | None = config.get(CONF_DEPARTURES_DURATION)
        self.walking_time: int = config.get(CONF_DEPARTURES_WALKING_TIME) or 1
        # we add +1 minute anyway to delete the "just gone" transport
        self.exclude_ringbahn_clockwise: bool = config.get(CONF_EXCLUDE_RINGBAHN_CLOCKWISE) or False
        self.exclude_ringbahn_counterclockwise: bool = config.get(CONF_EXCLUDE_RINGBAHN_COUNTERCLOCKWISE) or False
        self.show_api_line_colors: bool = config.get(CONF_SHOW_API_LINE_COLORS) or False
        self.session: CachedSession = CachedSession(
            backend='memory',
            cache_control=True,
            expire_after=timedelta(days=1)
        )

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
        return f"stop_{self.stop_id}_{self.sensor_name}_departures"

    @property
    def state(self) -> str:
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

    def update(self):
        self.departures = self.fetch_departures()

    def fetch_directional_departure(self, direction: str | None) -> list[Departure]:
        try:
            response = self.session.get(
                url=f"{API_ENDPOINT}/stops/{self.stop_id}/departures",
                params={
                    "when": (
                        datetime.utcnow() + timedelta(minutes=self.walking_time)
                    ).isoformat(),
                    "direction": direction,
                    "duration": self.duration,
                    "results": API_MAX_RESULTS,
                    "suburban": self.config.get(CONF_TYPE_SUBURBAN) or False,
                    "subway": self.config.get(CONF_TYPE_SUBWAY) or False,
                    "tram": self.config.get(CONF_TYPE_TRAM) or False,
                    "bus": self.config.get(CONF_TYPE_BUS) or False,
                    "ferry": self.config.get(CONF_TYPE_FERRY) or False,
                    "express": self.config.get(CONF_TYPE_EXPRESS) or False,
                    "regional": self.config.get(CONF_TYPE_REGIONAL) or False,
                },
                timeout=30,
            )
            response.raise_for_status()
        except HTTPError as ex:
            _LOGGER.warning(f"API error: {ex}")
            return []
        except Timeout as ex:
            _LOGGER.warning(f"API timeout: {ex}")
            return []

        _LOGGER.debug(f"OK: departures for {self.stop_id}: {response.text}")

        # parse JSON response
        try:
            departures = response.json()
        except InvalidJSONError as ex:
            _LOGGER.error(f"API invalid JSON: {ex}")
            return []

        if self.excluded_stops is None:
            excluded_stops = []
        else:
            excluded_stops = self.excluded_stops.split(",")

        # convert api data into objects
        return [
            Departure.from_dict(departure)
            for departure in departures.get("departures")
            if departure["stop"]["id"] not in excluded_stops
        ]

    def fetch_departures(self) -> list[Departure]:
        departures = []

        if self.direction is None:
            departures += self.fetch_directional_departure(self.direction)
        else:
            for direction in self.direction.split(','):
                departures += self.fetch_directional_departure(direction)

        # Ringbahn-Filter anwenden

        # The API-Response contains the symbols ⟲ and ⟳ as part of the direction value, e.g. "direction": "Ringbahn S42 ⟲"
        # We filter for them instead of hard-coding the line names (S41/S42). Maybe this is more future proof, otherwise below code
        # should be altered to filter for the line names instead.
        filtered_departures = [
            d for d in departures
            if not (
                (self.exclude_ringbahn_clockwise and d.direction and "⟳" in d.direction) or
                (self.exclude_ringbahn_counterclockwise and d.direction and "⟲" in d.direction)
            )
        ]
        
        # Get rid of duplicates
        # Duplicates should only exist for the Ringbahn and filtering for both
        # directions
        deduplicated_departures = set(departures)

        return sorted(deduplicated_departures, key=lambda d: d.timestamp)

    def next_departure(self):
        if self.departures and isinstance(self.departures, list):
            return self.departures[0]
        return None
