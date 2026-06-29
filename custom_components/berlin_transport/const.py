DOMAIN = "berlin_transport"

# Subentry type for stops added under a hub entry.
SUBENTRY_TYPE_STOP = "stop"
# Stable entity unique id, stored in subentry data (preserved across migration).
CONF_UNIQUE_ID = "unique_id"

# Defaults, used when the matching option is not configured on the entry.
DEFAULT_SCAN_INTERVAL = 90  # seconds
DEFAULT_FALLBACK_TIME = 15  # minutes
DEFAULT_API_ENDPOINT = "https://v6.vbb.transport.rest"
DEFAULT_API_MAX_RESULTS = 15

# Option keys (stored in ConfigEntry.options, edited via the options flow)
CONF_API_ENDPOINT = "api_endpoint"
CONF_API_MAX_RESULTS = "api_max_results"
CONF_FALLBACK_TIME = "fallback_time"

DEFAULT_ICON = "mdi:clock"

CONF_DEPARTURES = "departures"
CONF_DEPARTURES_NAME = "name"
CONF_DEPARTURES_STOP_ID = "stop_id"
CONF_SELECTED_STOP = "selected_stop"
CONF_DEPARTURES_EXCLUDED_STOPS = "excluded_stops"
CONF_DEPARTURES_EXCLUDED_LINES = "excluded_lines"
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
