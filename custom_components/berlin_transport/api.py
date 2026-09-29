import asyncio
import logging
from collections.abc import Mapping
from typing import Any

import aiohttp
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import (
    SERVER_SOFTWARE,
    async_get_clientsession,
)
from homeassistant.loader import async_get_integration

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


class TransportApi:
    def __init__(
        self,
        session: aiohttp.ClientSession,
        endpoint: str,
        user_agent: str,
    ) -> None:
        self.session = session
        self.endpoint = endpoint
        self.headers = {"User-Agent": user_agent}
        # Whether the last request failed. Every stop of a hub shares this
        # client and polls every 90 seconds, so an outage is only logged once
        # per client instead of once per stop and poll.
        self._failing = False

    async def _get(
        self,
        path: str,
        params: Mapping[str, Any],
        timeout: float = 30,
    ) -> Any:
        try:
            async with asyncio.timeout(timeout):
                response = await self.session.get(
                    f"{self.endpoint}{path}",
                    params=params,
                    headers=self.headers,
                )
                response.raise_for_status()
                result = await response.json()
        except TimeoutError:
            self._log_failure(path, f"no answer within {timeout} seconds")
            return None
        except aiohttp.ClientError as ex:
            self._log_failure(path, ex)
            return None
        except Exception as ex:  # pylint: disable=broad-exception-caught
            _LOGGER.error(f"Unexpected error for {path}: {ex}")
            return None

        if self._failing:
            self._failing = False
            _LOGGER.info("The API at %s works again", self.endpoint)
        return result

    def _log_failure(self, path: str, reason: object) -> None:
        """Log the first failed request as a warning, the ones after it as debug."""
        if self._failing:
            _LOGGER.debug("API request to %s%s failed: %s", self.endpoint, path, reason)
            return

        self._failing = True
        _LOGGER.warning(
            (
                "API request to %s%s failed: %s. Further errors are logged at "
                "debug level until the API works again"
            ),
            self.endpoint,
            path,
            reason,
        )

    async def locations(
        self, location_query: str, max_results: int
    ) -> list[dict[str, Any]] | None:
        result: list[dict[str, Any]] | None = await self._get(
            "/locations",
            {"query": location_query, "results": max_results},
        )
        return result

    async def stop(
        self, stop_id: str, params: Mapping[str, Any]
    ) -> dict[str, Any] | None:
        result: dict[str, Any] | None = await self._get(f"/stops/{stop_id}", params)
        return result

    async def departures(
        self, stop_id: int, params: Mapping[str, Any]
    ) -> dict[str, Any] | None:
        result: dict[str, Any] | None = await self._get(
            f"/stops/{stop_id}/departures", params
        )
        return result


type TransportConfigEntry = ConfigEntry[TransportApi]


async def async_create_api(hass: HomeAssistant, endpoint: str) -> TransportApi:
    integration = await async_get_integration(hass, DOMAIN)
    user_agent = (
        f"{SERVER_SOFTWARE} "
        f"home-assistant-berlin-transport/{integration.version} "
        f"(+{integration.documentation})"
    )
    return TransportApi(async_get_clientsession(hass), endpoint, user_agent)
