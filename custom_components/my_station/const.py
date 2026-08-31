"""Constants for the My Station integration."""

from __future__ import annotations

DOMAIN = "my_station"

CONF_ACCESS_ID = "access_id"
CONF_DURATION = "duration"
CONF_MAX_JOURNEYS = "max_journeys"
CONF_STOP_ID = "stop_id"
CONF_UPDATE_INTERVAL = "update_interval_minutes"

DEFAULT_DURATION = 60
DEFAULT_MAX_JOURNEYS = 80
DEFAULT_NAME = "My Station"
DEFAULT_STOP_ID = "8600626"
DEFAULT_UPDATE_INTERVAL = 60

MIN_DURATION = 1
MAX_DURATION = 1440
MIN_MAX_JOURNEYS = 1
MAX_MAX_JOURNEYS = 500
MIN_UPDATE_INTERVAL = 1
MAX_UPDATE_INTERVAL = 1440

CATEGORY_FILTER = "Re"
API_URL = "https://www.rejseplanen.dk/api/departureBoard"
API_TIMEOUT_SECONDS = 30

CARD_URL_PATH = "/my_station"
CARD_RESOURCE_URL = f"{CARD_URL_PATH}/my-station-card.js"
