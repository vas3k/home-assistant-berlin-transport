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
    time: datetime
    direction: str | None = None
    icon: str | None = None
    color: str | None = None
    location: tuple[float, float] | None = None

    @classmethod
    def from_dict(cls, source):
        line_type = source.get("line", {}).get("product")
        line_visuals = TRANSPORT_TYPE_VISUALS.get(line_type)
        return cls(
            trip_id=source["tripId"],
            line_name=source.get("line", {}).get("name"),
            line_type=source.get("line", {}).get("product"),
            time=datetime.fromisoformat(
                source.get("when") or source.get("plannedWhen")
            ).strftime("%H:%M"),
            direction=source.get("direction"),
            icon=line_visuals["icon"] if line_visuals else DEFAULT_ICON,
            color=line_visuals["color"]
            if line_visuals
            else source.get("line", {}).get("color", {}).get("bg"),
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
            "color": self.color,
        }
