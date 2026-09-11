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
    cancelled: bool
    delay: int | None
    warnings: list[dict[str, str]] | None
    walking_time: int


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
    fallback_color: str | None = None
    location: tuple[float, float] | None = None
    cancelled: bool = False
    delay: int | None = None
    warnings: list[dict[str, str]] | None = None

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

        current_trip_position = source.get("currentTripPosition", {})
        latitude = current_trip_position.get("latitude")
        longitude = current_trip_position.get("longitude")
        location = (
            (latitude, longitude)
            if latitude is not None and longitude is not None
            else None
        )

        return cls(
            trip_id=source.get("tripId", "unknown"),
            line_name=line.get("name"),  # type: ignore
            line_type=line_type,
            timestamp=timestamp,
            direction=source.get("direction"),
            icon=line_visuals.get("icon") or DEFAULT_ICON,
            bg_color=line.get("color", {}).get("bg"),
            fallback_color=line_visuals.get("color"),
            location=location,
            cancelled=source.get("cancelled", False),
            delay=source.get("delay", None),
            warnings=[
                {"id": r["id"], "summary": r["summary"]}
                for r in source.get("remarks", [])
                if r.get("type") == "warning" and r.get("summary")
            ]
            or None,
        )

    @cached_property
    def time(self) -> str:
        return self.timestamp.strftime("%H:%M")

    def to_dict(self, show_api_line_colors: bool, walking_time: int) -> DepartureDict:
        color = self.fallback_color
        if show_api_line_colors and self.bg_color is not None:
            color = self.bg_color
        return {
            "line_name": self.line_name,
            "line_type": self.line_type,
            "time": self.time,
            "timestamp": self.timestamp,
            "direction": self.direction,
            "color": color,
            "cancelled": self.cancelled,
            "delay": self.delay,
            "warnings": self.warnings,
            "walking_time": walking_time,
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
