from datetime import timedelta

DOMAIN = "berlin_transport"
SCAN_INTERVAL = timedelta(seconds=90)
API_ENDPOINT = "https://v6.vbb.transport.rest"
API_MAX_RESULTS = 15

DEFAULT_ICON = "mdi:clock"

CONF_DEPARTURES = "departures"
CONF_DEPARTURES_NAME = "name"
CONF_DEPARTURES_STOP_ID = "stop_id"
CONF_DEPARTURES_WALKING_TIME = "walking_time"
CONF_DEPARTURES_DIRECTION = "direction"
CONF_DEPARTURES_DURATION = "duration"
CONF_SHOW_API_LINE_COLORS = "show_official_line_colors"
CONF_TYPE_SUBURBAN = "suburban"
CONF_TYPE_SUBWAY = "subway"
CONF_TYPE_TRAM = "tram"
CONF_TYPE_BUS = "bus"
CONF_TYPE_FERRY = "ferry"
CONF_TYPE_EXPRESS = "express"
CONF_TYPE_REGIONAL = "regional"

TRANSPORT_TYPE_VISUALS = {
    CONF_TYPE_SUBURBAN: {
        "code": "S",
        "icon": "mdi:subway-variant",
        "color": "#008D4F",
    },
    CONF_TYPE_SUBWAY: {
        "code": "U",
        "icon": "mdi:subway",
        "color": "#2864A6",
    },
    CONF_TYPE_TRAM: {
        "code": "M",
        "icon": "mdi:tram",
        "color": "#D82020",
    },
    CONF_TYPE_BUS: {
        "code": "BUS",
        "icon": "mdi:bus",
        "color": "#A5027D"
    },
    CONF_TYPE_FERRY: {
        "code": "F",
        "icon": "mdi:ferry",
        "color": "#0080BA"
    },
    CONF_TYPE_EXPRESS: {
        "code": "Train",
        "icon": "mdi:train",
        "color": "#4D4D4D"
    },
    CONF_TYPE_REGIONAL: {
        "code": "RE",
        "icon": "mdi:train",
        "color": "#F01414"
    }
}
