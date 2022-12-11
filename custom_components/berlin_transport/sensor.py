"""The Berlin (BVG) and Brandenburg (VBB) transport integration."""
from __future__ import annotations
import logging
from typing import Optional
from datetime import datetime, timedelta

import requests
import voluptuous as vol

from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType
from homeassistant.components.sensor import SensorEntity
from homeassistant.components.sensor import PLATFORM_SCHEMA
from .const import (  # pylint: disable=unused-import
    DOMAIN,  # noqa
    SCAN_INTERVAL,  # noqa
    API_ENDPOINT,
    API_MAX_RESULTS,
    CONF_DEPARTURES,
    CONF_DEPARTURES_DIRECTION,
    CONF_DEPARTURES_STOP_ID,
    CONF_DEPARTURES_WALKING_TIME,
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
    vol.Optional(CONF_TYPE_SUBURBAN, default=True): bool,
    vol.Optional(CONF_TYPE_SUBWAY, default=True): bool,
    vol.Optional(CONF_TYPE_TRAM, default=True): bool,
    vol.Optional(CONF_TYPE_BUS, default=True): bool,
    vol.Optional(CONF_TYPE_FERRY, default=True): bool,
    vol.Optional(CONF_TYPE_EXPRESS, default=True): bool,
    vol.Optional(CONF_TYPE_REGIONAL, default=True): bool,
}

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Optional(CONF_DEPARTURES): [
            {
                vol.Required(CONF_DEPARTURES_NAME): str,
                vol.Required(CONF_DEPARTURES_STOP_ID): int,
                vol.Optional(CONF_DEPARTURES_DIRECTION): int,
                vol.Optional(CONF_DEPARTURES_WALKING_TIME, default=1): int,
                **TRANSPORT_TYPES_SCHEMA,
            }
        ]
    }
)


async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    add_entities: AddEntitiesCallback,
    _: DiscoveryInfoType | None = None,
) -> None:
    """Set up the sensor platform."""
    if CONF_DEPARTURES in config:
        for departure in config[CONF_DEPARTURES]:
            add_entities([TransportSensor(hass, departure)])


class TransportSensor(SensorEntity):
    departures: list[Departure] = []

    def __init__(self, hass: HomeAssistant, config: dict) -> None:
        self.hass: HomeAssistant = hass
        self.config: dict = config
        self.stop_id: int = config[CONF_DEPARTURES_STOP_ID]
        self.sensor_name: str | None = config.get(CONF_DEPARTURES_NAME)
        self.direction: int | None = config.get(CONF_DEPARTURES_DIRECTION)
        self.walking_time: int = config.get(CONF_DEPARTURES_WALKING_TIME) or 1
        # we add +1 minute anyway to delete the "just gone" transport

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
            "departures": [departure.to_dict() for departure in self.departures or []]
        }

    def update(self):
        self.departures = self.fetch_departures()

    def fetch_departures(self) -> Optional[list[Departure]]:
        try:
            response = requests.get(
                url=f"{API_ENDPOINT}/stops/{self.stop_id}/departures",
                params={
                    "when": (
                        datetime.utcnow() + timedelta(minutes=self.walking_time)
                    ).isoformat(),
                    "direction": self.direction,
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
        except requests.exceptions.HTTPError as ex:
            _LOGGER.warning(f"API error: {ex}")
            return []
        except requests.exceptions.Timeout as ex:
            _LOGGER.warning(f"API timeout: {ex}")
            return []

        _LOGGER.debug(f"OK: departures for {self.stop_id}: {response.text}")

        # parse JSON response
        try:
            departures = response.json()
        except requests.exceptions.InvalidJSONError as ex:
            _LOGGER.error(f"API invalid JSON: {ex}")
            return []

        # convert api data into objects
        return [Departure.from_dict(departure) for departure in departures]

    def next_departure(self):
        if self.departures and isinstance(self.departures, list):
            return self.departures[0]
        return None
