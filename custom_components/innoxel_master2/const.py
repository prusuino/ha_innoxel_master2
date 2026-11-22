"""Constants of the Innoxel Master 2 integration."""
from __future__ import annotations

DOMAIN = "innoxel_master2"
DEFAULT_PORT = 4001

# Output and dimmer states are polled; the master has no push channel.
SCAN_INTERVAL = 2
# The weather station is read on every n-th state poll.
WEATHER_EVERY = 15
# Delay between a simulated key and the state read that follows it.
REFRESH_DELAY = 0.3

# Subentry types: one subentry is one channel the user added.
SUBENTRY_SWITCH = "switch"
SUBENTRY_LIGHT = "light"
SUBENTRY_DIMMER = "dimmer"
SUBENTRY_COVER = "cover"
SUBENTRY_BUTTON = "button"

CONF_KEY = "key"
CONF_OUTPUT = "output"
CONF_DIMMER = "dimmer"
CONF_KEY_UP = "key_up"
CONF_KEY_DOWN = "key_down"
CONF_OUTPUT_UP = "output_up"
CONF_OUTPUT_DOWN = "output_down"

SERVICE_SEND_KEY = "send_key"
ATTR_ADDRESS = "address"
ATTR_ACTION = "action"
ATTR_CONFIG_ENTRY_ID = "config_entry_id"
