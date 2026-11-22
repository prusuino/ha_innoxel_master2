"""Constants of the Innoxel Master 2 integration."""
from __future__ import annotations

DOMAIN = "innoxel_master2"
DEFAULT_PORT = 4001

# Output and dimmer states are polled; the master has no push channel. One
# state poll takes about 45 ms on a Master 2 (REV 09.23), measured through a
# Moxa NPort at 115200 baud.
SCAN_INTERVAL = 1
# The weather station is read on every n-th state poll (every 30 seconds).
WEATHER_EVERY = 30
# After a simulated key the state is read back at once: the master answers
# the key only when it has carried it out, and the first poll afterwards
# already showed the new state in every measurement. Should the expected
# change not be there yet, the read is repeated this often, this far apart.
REFRESH_TRIES = 10
REFRESH_STEP = 0.1

# Subentry types: one subentry is one channel the user added.
SUBENTRY_SWITCH = "switch"
SUBENTRY_LIGHT = "light"
SUBENTRY_DIMMER = "dimmer"
SUBENTRY_COVER = "cover"
SUBENTRY_BUTTON = "button"
SUBENTRY_SENSOR = "sensor"

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
