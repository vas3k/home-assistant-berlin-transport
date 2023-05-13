from dataclasses import dataclass
from datetime import datetime

from .const import TRANSPORT_TYPE_VISUALS, DEFAULT_ICON


@dataclass
class Departure:
    """Departure dataclass to store data from API:
    https://v5.vbb.transport.rest/api.html#get-stopsiddepartures"""

    trip_id: str
    line_name: str
    line_type: str
    timestamp: datetime
    time: datetime
    direction: str | None = None
    icon: str | None = None
    bg_color: str | None = None
    fallback_color: str | None = None
    location: tuple[float, float] | None = None

    @classmethod
    def from_dict(cls, source):
        line_desc = source.get("line", {})
        line_type = line_desc.get("product")
        line_name = line_desc.get("name")
        line_visuals = TRANSPORT_TYPE_VISUALS.get(line_type) or {}
        line_color = line_visuals.get("line_colors").get(line_name)
        timestamp=datetime.fromisoformat(source.get("when") or source.get("plannedWhen"))
        return cls(
            trip_id=source["tripId"],
            line_name=line_name,
            line_type=line_type,
            timestamp=timestamp,
            time=timestamp.strftime("%H:%M"),
            direction=source.get("direction"),
            icon=line_visuals.get("icon") or DEFAULT_ICON,
            bg_color=line_color,
            fallback_color=line_visuals.get("product_color"),
            location=[
                source.get("currentTripPosition", {}).get("latitude") or 0.0,
                source.get("currentTripPosition", {}).get("longitude") or 0.0,
            ],
        )

    def to_dict(self):
        return {
            "line_name": self.line_name,
            "line_type": self.line_type,
            "time": self.time,
            "direction": self.direction,
            "color": self.bg_color or self.fallback_color,
        }
