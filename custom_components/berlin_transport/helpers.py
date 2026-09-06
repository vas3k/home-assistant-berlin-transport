"""Shared helpers for the Berlin (BVG) and Brandenburg (VBB) transport integration."""

from typing import Any, Mapping

from .const import CONF_LIST_OPTIONS


def as_string_list(value: Any) -> list[str]:
    """Normalize a list option into a list of non-empty strings.

    A plain string is read as the legacy comma-separated form, so YAML configs
    written before the switch to lists keep working.
    """
    if value is None:
        return []
    if isinstance(value, str):
        return value.split(",")
    if isinstance(value, list):
        return value
    if isinstance(value, tuple):
        return list(value)
    return [value]


def is_legacy_csv(value: Any) -> bool:
    """Whether a value still uses the comma-separated string form."""
    return isinstance(value, str) and "," in value


def normalized_list_options(data: Mapping[str, Any]) -> dict[str, list[str]]:
    """The list options of `data`, normalized to lists of strings.

    Only options actually present are returned, so the result can be merged
    into stored data without introducing keys the user never set.
    """
    return {key: as_string_list(data[key]) for key in CONF_LIST_OPTIONS if key in data}
