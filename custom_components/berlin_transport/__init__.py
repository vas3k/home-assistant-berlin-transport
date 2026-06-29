"""The Berlin (BVG) and Brandenburg (VBB) transport integration."""
from __future__ import annotations

import logging
from types import MappingProxyType

from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry, ConfigSubentry
from homeassistant.const import Platform
from homeassistant.helpers.typing import ConfigType

from .const import (
    DOMAIN, # noqa
    CONF_API_ENDPOINT,
    CONF_API_MAX_RESULTS,
    CONF_FALLBACK_TIME,
    CONF_UNIQUE_ID,
    SUBENTRY_TYPE_STOP,
)

_LOGGER = logging.getLogger(__name__)

PLATFORMS = [Platform.SENSOR]

# Keys that live on the hub entry; everything else describes a single stop.
_HUB_KEYS = (CONF_API_ENDPOINT, CONF_API_MAX_RESULTS, CONF_FALLBACK_TIME)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up a config entry."""
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(config_entry_update_listener))
    return True


async def async_migrate_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Migrate v1 (one entry per stop) to v2 (hub entry + stop subentries)."""
    if entry.version > 2:
        # Downgrade is not supported.
        return False

    if entry.version == 1:
        old = dict(entry.data)
        hub_data = {key: old[key] for key in _HUB_KEYS if key in old}
        # The remaining keys describe the single stop this entry used to be.
        stop_data = {k: v for k, v in old.items() if k not in _HUB_KEYS}
        # Preserve the existing entity identity (was keyed on the entry id).
        stop_data[CONF_UNIQUE_ID] = entry.entry_id

        subentry = ConfigSubentry(
            data=MappingProxyType(stop_data),
            subentry_type=SUBENTRY_TYPE_STOP,
            title=entry.title,
            unique_id=None,
        )

        hass.config_entries.async_update_entry(
            entry,
            data=hub_data,
            version=2,
        )
        hass.config_entries.async_add_subentry(entry, subentry)
        _LOGGER.info("Migrated %s to hub + stop subentry layout", entry.title)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def config_entry_update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Update listener, called when the config entry options are changed."""
    await hass.config_entries.async_reload(entry.entry_id)


def setup(
    hass: HomeAssistant, config: ConfigType  # pylint: disable=unused-argument
) -> bool:
    return True
