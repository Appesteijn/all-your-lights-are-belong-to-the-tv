DOMAIN = "ambient_tv"

CONF_ADB_HOST = "adb_host"
CONF_ADB_PORT = "adb_port"
CONF_LIGHTS = "lights"
CONF_UPDATE_INTERVAL_MS = "update_interval_ms"
CONF_TRANSITION = "transition"
CONF_BRIGHTNESS_FACTOR = "brightness_factor"
CONF_SATURATION_BOOST = "saturation_boost"
CONF_CHANGE_THRESHOLD = "change_threshold"

DEFAULT_ADB_PORT = 5555
DEFAULT_UPDATE_INTERVAL_MS = 500
DEFAULT_TRANSITION = 0.3
DEFAULT_BRIGHTNESS_FACTOR = 1.0
DEFAULT_SATURATION_BOOST = 1.4
DEFAULT_CHANGE_THRESHOLD = 12

ZONE_LEFT = "left"
ZONE_RIGHT = "right"
ZONE_CEILING = "ceiling"

ZONE_LABELS = {
    ZONE_LEFT: "Links (hoek achter kijker)",
    ZONE_RIGHT: "Rechts (hoek achter kijker + schouw)",
    ZONE_CEILING: "Plafond (kleurtemperatuur)",
}

ADB_KEY_PATH = ".adb/adbkey"
