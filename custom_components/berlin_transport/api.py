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
                return await response.json()
        except TimeoutError as ex:
            _LOGGER.warning(f"API timeout for {path}: {ex}")
            return None
        except aiohttp.ClientError as ex:
            _LOGGER.warning(f"API error for {path}: {ex}")
            return None
        except Exception as ex:  # pylint: disable=broad-exception-caught
            _LOGGER.error(f"Unexpected error for {path}: {ex}")
            return None

    async def locations(
        self, location_query: str, max_results: int
    ) -> list[dict[str, Any]] | None:
        result: list[dict[str, Any]] | None = await self._get(
            "/locations",
            {"query": location_query, "results": max_results},
        )
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
