import asyncio
from collections.abc import Mapping
from typing import Any

import aiohttp
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession


class TransportApi:
    def __init__(self, session: aiohttp.ClientSession, endpoint: str) -> None:
        self.session = session
        self.endpoint = endpoint

    async def _get(
        self,
        path: str,
        params: Mapping[str, Any],
        timeout: float = 30,
    ) -> Any:
        async with asyncio.timeout(timeout):
            response = await self.session.get(f"{self.endpoint}{path}", params=params)
            response.raise_for_status()
            return await response.json()

    async def locations(self, location_query: str, max_results: int) -> Any:
        return await self._get(
            "/locations",
            {"query": location_query, "results": max_results},
        )

    async def departures(self, stop_id: int, params: Mapping[str, Any]) -> Any:
        return await self._get(f"/stops/{stop_id}/departures", params)
