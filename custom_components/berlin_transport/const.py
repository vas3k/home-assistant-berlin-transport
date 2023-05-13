from datetime import timedelta

DOMAIN = "berlin_transport"
SCAN_INTERVAL = timedelta(seconds=90)
API_ENDPOINT = "https://v5.vbb.transport.rest"
API_MAX_RESULTS = 15

DEFAULT_ICON = "mdi:clock"

CONF_DEPARTURES = "departures"
CONF_DEPARTURES_NAME = "name"
CONF_DEPARTURES_STOP_ID = "stop_id"
CONF_DEPARTURES_WALKING_TIME = "walking_time"
CONF_DEPARTURES_DIRECTION = "direction"
CONF_TYPE_SUBURBAN = "suburban"
CONF_TYPE_SUBWAY = "subway"
CONF_TYPE_TRAM = "tram"
CONF_TYPE_BUS = "bus"
CONF_TYPE_FERRY = "ferry"
CONF_TYPE_EXPRESS = "express"
CONF_TYPE_REGIONAL = "regional"

TRANSPORT_TYPE_VISUALS = {
    CONF_TYPE_SUBURBAN: {
        "product_code": "S",
        "product_icon": "mdi:subway-variant",
        "product_color": "#008D4F",
        "line_colors": {
            "S1" : "#da6ba2",
            "S2" : "#007734",
            "S25": "#007734",
            "S26": "#007734",
            "S3" : "#0066ad",
            "S41": "#ad5937",
            "S42": "#cb6418",
            "S45": "#cd9c53",
            "S46": "#cd9c53",
            "S47": "#cd9c53",
            "S5" : "#eb7405",
            "S7" : "#816da6",
            "S75": "#816da6",
            "S8" : "#66aa22",
            "S85": "#66aa22",
            "S9" : "#992746",
        }
    },
    CONF_TYPE_SUBWAY: {
        "product_code": "U",
        "product_icon": "mdi:subway",
        "product_color": "#2864A6",
        "line_colors": {
            "U1": "#7dad4c",
            "U2": "#da421e",
            "U3": "#16683d",
            "U4": "#f0d722",
            "U5": "#7e5330",
            "U6": "#8c6dab",
            "U7": "#009bd5",
            "U8": "#224f86",
            "U9": "#f3791d",
        }
    },
    CONF_TYPE_TRAM: {
        "product_code": "M",
        "product_icon": "mdi:tram",
        "product_color": "#D82020",
        "line_colors": {}
    },
    CONF_TYPE_BUS: {
        "product_code": "BUS",
        "product_icon": "mdi:bus",
        "product_color": "#A5027D",
        "line_colors": {}
    },
    CONF_TYPE_FERRY: {
        "product_code": "F",
        "product_icon": "mdi:ferry",
        "product_color": "#0080BA",
        "line_colors": {}
    },
    CONF_TYPE_EXPRESS: {
        "product_code": "Train",
        "product_icon": "mdi:train",
        "product_color": "#4D4D4D",
        "line_colors": {}
    },
    CONF_TYPE_REGIONAL: {
        "product_code": "RE",
        "product_icon": "mdi:train",
        "product_color": "#F01414",
        "line_colors": {
            "FEX" :"#79122f",
            "RB10":"#66aa22",
            "RB12":"#a5027d",
            "RB14":"#a5027d",
            "RB20":"#007734",
            "RB21":"#501689",
            "RB22":"#009bd5",
            "RB23":"#eb7405",
            "RB24":"#da6ba2",
            "RB25":"#007cb0",
            "RB26":"#009686",
            "RB27":"#e2001a",
            "RB31":"#66aa22",
            "RB32":"#697c8a",
            "RB33":"#a5027d",
            "RB34":"#0066ad",
            "RB35":"#816da6",
            "RB36":"#ad5937",
            "RB37":"#ad5937",
            "RB43":"#009bd5",
            "RB45":"#ffd502",
            "RB46":"#da6ba2",
            "RB49":"#992746",
            "RB51":"#da6ba2",
            "RB54":"#816da6",
            "RB55":"#eb7405",
            "RB60":"#66aa22",
            "RB61":"#992746",
            "RB62":"#da6ba2",
            "RB63":"#ffd502",
            "RB65":"#0066ad",
            "RB66":"#007734",
            "RB73":"#009686",
            "RB74":"#0066ad",
            "RB91":"#eb7405",
            "RB92":"#eb7405",
            "RB93":"#eb7405",
            "RE1" :"#e2001a",
            "RE10":"#5e5e5d",
            "RE14":"#a98956",
            "RE15":"#ffd502",
            "RE18":"#eb7405",
            "RE2" :"#ffd502",
            "RE3" :"#eb7405",
            "RE4" :"#992746",
            "RE5" :"#0066ad",
            "RE6" :"#da6ba2",
            "RE66":"#007734",
            "RE7" :"#007734",
            "RE8" :"#501689",
        }
    }
}
