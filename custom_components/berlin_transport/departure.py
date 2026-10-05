from dataclasses import dataclass
from datetime import datetime
from functools import cached_property
from typing import Any, TypedDict

from .const import DEFAULT_ICON, TRANSPORT_TYPE_VISUALS


class DepartureDict(TypedDict):
    line_name: str
    line_type: str
    time: str
    timestamp: datetime
    direction: str | None
    color: str | None
    # Text color that goes with `color`. Only set for the official line colors,
    # the default colors all work with white text.
    text_color: str | None
    cancelled: bool
    delay: int | None
    warnings: list[dict[str, str]] | None
    walking_time: int
    # `platform` differs from `planned_platform` when the platform changed.
    platform: str | None
    planned_platform: str | None
    # Only set when the departure leaves from another stop than the one
    # configured, e.g. a nearby stop of the same station.
    other_stop_name: str | None


@dataclass
class Departure:
    """Departure dataclass to store data from API:
    https://v6.vbb.transport.rest/api.html#get-stopsiddepartures"""

    trip_id: str
    line_name: str
    line_type: str
    timestamp: datetime
    icon: str
    direction: str | None = None
    bg_color: str | None = None
    fg_color: str | None = None
    fallback_color: str | None = None
    location: tuple[float, float] | None = None
    cancelled: bool = False
    delay: int | None = None
    warnings: list[dict[str, str]] | None = None
    platform: str | None = None
    planned_platform: str | None = None
    stop_id: str | None = None
    stop_name: str | None = None
    # As sent by the API, only used to tell departures apart.
    planned_when: str | None = None

    @classmethod
    def from_dict(cls, source: dict[str, Any]) -> "Departure":
        line = source.get("line") or {}
        line_type: str = line.get("product")  # type: ignore
        line_visuals = TRANSPORT_TYPE_VISUALS.get(line_type) or {}
        when = source.get("when") or source.get("plannedWhen")
        if when is None:
            # Fallback if no time is provided
            timestamp = datetime.now().astimezone()
        else:
            try:
                timestamp = datetime.fromisoformat(when).astimezone()
            except ValueError:
                timestamp = datetime.now().astimezone()

        current_trip_position = source.get("currentTripPosition") or {}
        latitude = current_trip_position.get("latitude")
        longitude = current_trip_position.get("longitude")
        location = (
            (latitude, longitude)
            if latitude is not None and longitude is not None
            else None
        )

        line_color = line.get("color") or {}
        stop = source.get("stop") or {}

        return cls(
            trip_id=source.get("tripId") or "unknown",
            line_name=line.get("name"),  # type: ignore
            line_type=line_type,
            timestamp=timestamp,
            direction=source.get("direction"),
            icon=line_visuals.get("icon") or DEFAULT_ICON,
            bg_color=line_color.get("bg"),
            fg_color=line_color.get("fg"),
            fallback_color=line_visuals.get("color"),
            location=location,
            cancelled=source.get("cancelled") or False,
            delay=source.get("delay"),
            warnings=[
                {"id": r["id"], "summary": r["summary"]}
                for r in source.get("remarks") or []
                if r.get("type") == "warning" and r.get("summary") and r.get("id")
            ]
            or None,
            platform=source.get("platform"),
            planned_platform=source.get("plannedPlatform"),
            stop_id=stop.get("id"),
            stop_name=stop.get("name"),
            planned_when=source.get("plannedWhen"),
        )

    @cached_property
    def time(self) -> str:
        return self.timestamp.strftime("%H:%M")

    def to_dict(
        self,
        show_api_line_colors: bool,
        walking_time: int,
        stop_id: str | int | None = None,
    ) -> DepartureDict:
        """The departure as shown in the sensor's `departures` attribute.

        `stop_id` is the configured stop, departures from other stops get the
        name of the stop they leave from.
        """
        color = self.fallback_color
        text_color = None
        if show_api_line_colors and self.bg_color is not None:
            color = self.bg_color
            text_color = self.fg_color
        other_stop_name = None
        if stop_id is not None and self.stop_id != str(stop_id):
            other_stop_name = self.stop_name
        return {
            "line_name": self.line_name,
            "line_type": self.line_type,
            "time": self.time,
            "timestamp": self.timestamp,
            "direction": self.direction,
            "color": color,
            "text_color": text_color,
            "cancelled": self.cancelled,
            "delay": self.delay,
            "warnings": self.warnings,
            "walking_time": walking_time,
            "platform": self.platform,
            "planned_platform": self.planned_platform,
            "other_stop_name": other_stop_name,
        }

    # Make the object hashable and use all infos that can be displayed in the
    # frontend
    def __hash__(self) -> int:
        # The value of colors and walking time doesn't matter, it just needs to
        # be the same for all evaluations of this function
        d = self.to_dict(show_api_line_colors=False, walking_time=0)
        # Copy to a normal dictionary, so we don't have type errors when
        # exchanging warnings with a hashable tuple instead of a dict
        hashable = dict(d)
        # Warnings are dicts (not hashable), replace with a sorted tuple of IDs
        hashable["warnings"] = (
            tuple(sorted(w["id"] for w in d["warnings"])) if d["warnings"] else None
        )
        # Dictionaries are not hashable, so use the items, sort them for
        # reproducibility. Convert it to a tuple, since lists are also not
        # hashable
        return hash(tuple(sorted(hashable.items())))
