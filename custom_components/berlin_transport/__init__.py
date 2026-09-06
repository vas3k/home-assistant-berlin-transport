"""The Berlin (BVG) and Brandenburg (VBB) transport integration."""

from __future__ import annotations

import logging
from types import MappingProxyType

from homeassistant.config_entries import ConfigEntry, ConfigSubentry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.typing import ConfigType

from .const import (
    DOMAIN,  # noqa
    CONF_API_ENDPOINT,
    CONF_API_MAX_RESULTS,
    CONF_FALLBACK_TIME,
    CONF_UNIQUE_ID,
    CONFIG_ENTRY_VERSION,
    DEFAULT_API_ENDPOINT,
    SUBENTRY_TYPE_STOP,
)
from .helpers import normalized_list_options

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
    """Migrate an entry to the current version.

    v1 -> v2: one entry per stop becomes a single hub entry with one subentry
    per stop. All v1 entries end up in a single hub: the first one to be
    migrated becomes that hub, every later one hands its stop over as a
    subentry and is removed. The shared settings of that first entry become the
    hub's and from then on apply to every stop under it.

    v2 -> v3: the options that used to hold a comma-separated string become
    real lists of strings.
    """
    if entry.version > CONFIG_ENTRY_VERSION:
        # Downgrade is not supported.
        return False

    if entry.version == 2:
        _migrate_lists(hass, entry)
        return True

    if entry.version != 1:
        return True

    old = dict(entry.data)
    hub_settings = {key: old[key] for key in _HUB_KEYS if key in old}
    # The remaining keys describe the single stop this entry used to be.
    stop_data = {k: v for k, v in old.items() if k not in _HUB_KEYS}
    # v1 predates the list options, so bring the stop straight to v3 shape: it
    # may well be handed to a hub that has already been migrated.
    stop_data.update(normalized_list_options(stop_data))
    # Preserve the existing entity identity (was keyed on the entry id).
    stop_data[CONF_UNIQUE_ID] = entry.entry_id
    stop_title = entry.title

    hub = _existing_hub(hass, entry)

    if hub is None:
        # First one through: this entry becomes the hub the others join.
        hass.config_entries.async_update_entry(
            entry,
            data={},
            options=hub_settings,
            title=hub_settings.get(CONF_API_ENDPOINT) or DEFAULT_API_ENDPOINT,
            version=CONFIG_ENTRY_VERSION,
        )
        hub = entry

    subentry = ConfigSubentry(
        data=MappingProxyType(stop_data),
        subentry_type=SUBENTRY_TYPE_STOP,
        title=stop_title,
        unique_id=None,
    )
    hass.config_entries.async_add_subentry(hub, subentry)

    # Move the existing entity to the subentry. Do this before the entry is
    # removed, which would remove the entity_id with it.
    registry = er.async_get(hass)
    for registry_entry in er.async_entries_for_config_entry(registry, entry.entry_id):
        registry.async_update_entity(
            registry_entry.entity_id,
            config_entry_id=hub.entry_id,
            config_subentry_id=subentry.subentry_id,
        )

    # Remove old config entries for every entry that has not become the hub
    if hub is not entry:
        # Schedule removal once the setup lock which is held by us right now,
        # is gone
        hass.async_create_task(_async_drop_migrated_entry(hass, entry, hub))

    _LOGGER.info("Migrated %s into the %s hub", stop_title, hub.title)
    return True


def _migrate_lists(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Rewrite every stop's comma-separated string options as lists of strings."""
    for subentry in list(entry.subentries.values()):
        if subentry.subentry_type != SUBENTRY_TYPE_STOP:
            continue
        hass.config_entries.async_update_subentry(
            entry,
            subentry,
            data={**subentry.data, **normalized_list_options(subentry.data)},
        )

    hass.config_entries.async_update_entry(entry, version=CONFIG_ENTRY_VERSION)
    _LOGGER.info("Migrated the %s hub to list-valued stop options", entry.title)


def _existing_hub(hass: HomeAssistant, entry: ConfigEntry) -> ConfigEntry | None:
    """Return the hub to migrate into, if there already is one."""
    for other in hass.config_entries.async_entries(DOMAIN):
        if other.entry_id != entry.entry_id and other.version >= 2:
            return other
    return None


async def _async_drop_migrated_entry(
    hass: HomeAssistant, entry: ConfigEntry, hub: ConfigEntry
) -> None:
    """Remove an entry whose stop now lives in the hub, then reload the hub."""
    await hass.config_entries.async_remove(entry.entry_id)
    # Avoid race condition of an existing hub starting setup before all stops
    # were added
    await hass.config_entries.async_reload(hub.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def config_entry_update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Update listener, called when the config entry options are changed."""
    await hass.config_entries.async_reload(entry.entry_id)


def setup(
    hass: HomeAssistant,  # pylint: disable=unused-argument
    config: ConfigType,  # pylint: disable=unused-argument
) -> bool:
    return True
