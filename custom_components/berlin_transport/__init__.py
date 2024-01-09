"""The Berlin (BVG) and Brandenburg (VBB) transport integration."""
from __future__ import annotations

from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType

from .const import DOMAIN, SCAN_INTERVAL  # noqa

PLATFORMS = [Platform.SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up a config entry."""
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(config_entry_update_listener))
    return True


async def config_entry_update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Update listener, called when the config entry options are changed."""
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


def setup(
    hass: HomeAssistant, config: ConfigType  # pylint: disable=unused-argument
) -> bool:
    return True
