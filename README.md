# Innoxel Master 2 — Home Assistant Integration

![Innoxel Master 2](readme_header.png)

[![License: GPL v3](https://img.shields.io/badge/License-GPLv3-blue.svg)](LICENSE)
[![Release](https://img.shields.io/github/v/release/prusuino/ha_innoxel_master2)](https://github.com/prusuino/ha_innoxel_master2/releases)
[![Validate](https://github.com/prusuino/ha_innoxel_master2/actions/workflows/validate.yml/badge.svg)](https://github.com/prusuino/ha_innoxel_master2/actions/workflows/validate.yml)
[![Tests](https://github.com/prusuino/ha_innoxel_master2/actions/workflows/tests.yml/badge.svg)](https://github.com/prusuino/ha_innoxel_master2/actions/workflows/tests.yml)
[![Home Assistant](https://img.shields.io/badge/dynamic/json?url=https%3A%2F%2Fraw.githubusercontent.com%2Fprusuino%2Fha_innoxel_master2%2Fmain%2Fhacs.json&query=%24.homeassistant&label=Home%20Assistant&suffix=%2B&color=41BDF5)](https://www.home-assistant.io/)
[![Quality scale](https://img.shields.io/badge/Quality%20Scale-Bronze-cd7f32.svg)](https://developers.home-assistant.io/docs/core/integration-quality-scale/)
<a href="https://www.buymeacoffee.com/prusuino"><img src="https://cdn.buymeacoffee.com/buttons/v2/default-yellow.png" alt="Buy Me a Coffee" height="20"></a>

A native Home Assistant custom integration for the **Innoxel Master 2** (NOXmaster) home automation controller. The Master 2 has no network port; the integration talks to it through a serial device server such as a Moxa NPort — no cloud, no extra gateway software.

> This is an independent, community-built integration. It is **not affiliated with or endorsed by Innoxel**, and does not use any Innoxel trademarks or branding.

> **Tested on a bench.** Developed and tested with a Master 2 and one Switch 8 module. Dimmers, blinds and the weather station follow the protocol but have not been verified on real hardware yet — reports are welcome.

For the **Innoxel Master 3** use [ha_innoxel_master3](https://github.com/prusuino/ha_innoxel_master3) instead.

## Highlights

- **Local and direct**: talks the serial protocol of the master through a serial device server on your own network — no cloud, no extra gateway software.
- **Works like a wall button**: Home Assistant presses the keys you programmed in INNOXEL Setup and reads the real state of the outputs back.
- **Switches and lights with true state**: a command only presses the key when the output is in the other state, so two automations never cancel each other out.
- **Blinds**: one key impulse runs a blind to its end position, an impulse while it moves stops it.
- **Outputs found for you**: leave the output address empty and the integration detects which output a key switches.
- **Weather station**: temperature, wind speed, sun brightness east/south/west, twilight and rain appear on their own when a weather station is connected.
- **Long key presses**: the `send_key` action sends an impulse, or press and release separately.
- **INNOXEL Setup stays usable**: one switch releases the connection to the device server while you reprogram the master.

## Why this exists

The Master 2 predates the network-enabled Master 3: its only interface is an RS-232 port, which the manufacturer's own PC and phone remote controls reach through a serial device server. This integration speaks the same protocol, so a Master 2 installation gets real entities in Home Assistant without replacing the controller.

## What it provides

| Channel type | What you enter | What you get |
|---|---|---|
| Switch | key, output (detected when left empty) | `switch` with the real state |
| Light | key, output (detected when left empty) | `light` with the real state |
| Dimmer | key, dimmer channel | on/off `light`, the dim value as attribute `dim_value` |
| Blind | key up, key down, optionally the two motor outputs | `cover` with open, close and stop |
| Key | key | `button`, e.g. for a scene programmed in the master |

In addition:

- **Weather station**: temperature, wind speed, sun east/south/west, twilight and a rain sensor. They are created the first time the master reports valid weather data, so an installation without a weather station gets no empty entities.
- **Connection to the master**: a switch that releases the device server, see [Working with INNOXEL Setup](#working-with-innoxel-setup).
- **Action `innoxel_master2.send_key`**: sends a key impulse, or `press` and `release` separately for a long key press (dimming, jogging a blind).

### Addresses

Addresses use the notation of the Innoxel software:

| Kind | Example | Meaning |
|---|---|---|
| Output | `O0-3` | switch/motor module 0, output 3 (outputs 0–7) |
| Input | `I10-1` | input module 10, key 1 (keys 1–4) |
| Dimmer | `D0-2` | dimmer module 0, channel 2 (channels 0–3) |

For inputs the event number shown in INNOXEL Setup works as well: `GR28` is the same key as `I10-1` (the hexadecimal number divided by four is the module, the remainder plus one the key).

## Cover behavior

A blind is driven by its two keys, exactly like the wall button:

- **Open / close** sends a short impulse on the up or down key, which is a full run to the end position.
- **Stop** sends an impulse on the key of the running direction. With the motor outputs configured the direction is read from the master; without them the integration uses the direction of its own last command.
- The master does not know the position of a blind, so the cover reports only *opening* and *closing* (with the motor outputs configured) and no position.

To jog a blind, send a long key press with the action:

```yaml
- action: innoxel_master2.send_key
  data:
    address: I12-1
    action: press
- delay:
    milliseconds: 400
- action: innoxel_master2.send_key
  data:
    address: I12-1
    action: release
```

## Installation

Requires Home Assistant **2025.4** or newer.

### Home Assistant Marketplace or HACS (custom repository)

1. Use the button, which opens the repository directly in your Marketplace (Home Assistant 2026.11 or newer) or in HACS, and download the integration:

   [![Open in Marketplace](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=prusuino&repository=ha_innoxel_master2&category=integration)

   Without the button: add `https://github.com/prusuino/ha_innoxel_master2` as a custom repository of the type *Integration*.

2. Restart Home Assistant.

### Manual

1. Copy the `custom_components/innoxel_master2` folder into your Home Assistant `config/custom_components/` directory.
2. Restart Home Assistant.

## Setup

1. Go to **Settings → Devices & Services → Add Integration** and search for **"Innoxel Master 2"**.
2. Enter the **host** (IP address of the serial device server) and the **TCP port** (default `4001`). The integration asks the master for its firmware revision; setup only succeeds when a Master 2 answers.
3. Open the new entry and add your channels with **Add switch**, **Add light**, **Add dimmer**, **Add blind** or **Add key**. Each channel gets a name and the key that operates it.

For a switch or a light the output address can stay empty. The integration then presses the key twice and watches which output changes — the output ends in the state it had. Use this only where a brief switching does no harm, and enter the address by hand otherwise.

Every channel can be changed later through its **Reconfigure** menu, or deleted.

## FAQ: access to the Master 2

The Master 2 has no network port and no user accounts. Home Assistant reaches it through the RS-232 port, a serial device server and the keys you program in INNOXEL Setup.

### What you need

- An Innoxel Master 2 connected by RS-232 to a **serial device server** (serial-to-Ethernet converter). A Moxa NPort 5110 is tested; other device servers with a raw TCP server mode should work the same way.
- The device server configured as described in [Serial device server](#serial-device-server).
- **Keys programmed in INNOXEL Setup** for everything Home Assistant should control. The integration operates the installation the way a wall button does; it cannot switch an output directly. Virtual keys (touch panel events) are ideal: they need no hardware and do not collide with real buttons.

### Serial device server

The Master 2 expects the serial settings below; they are the ones from Innoxel's own guide for the Moxa NPort 5110. On a Moxa NPort they are set in the web console (`http://<address of the NPort>`) — do not forget **Save/Restart**, a plain *Submit* is not enough.

**Network Settings**

| Setting | Value |
|---|---|
| IP configuration | Static, or DHCP with a fixed lease in your router — the address must not change |

**Serial Settings → Port 1**

| Setting | Value |
|---|---|
| Baud rate | 115200 |
| Data bits | 8 |
| Stop bits | 1 |
| Parity | None |
| Flow control | None |
| FIFO | Enable |
| Interface | RS-232 |

**Operating Settings → Port 1**

| Setting | Value |
|---|---|
| Operation mode | TCP Server Mode |
| Local TCP port | 4001 (the port you enter in Home Assistant) |
| Max connection | 1 |
| TCP alive check time | 7 min |
| Inactivity time | 30000 ms |
| Ignore jammed IP | No |
| Allow driver control | No |
| Packing length | 0 |
| Delimiter 1 | `0D`, enabled |
| Delimiter 2 | disabled |
| Delimiter process | Do Nothing |
| Force transmit | 0 ms |

Notes:

- *Real COM Mode*, which older versions of INNOXEL Setup needed, does **not** work — the integration needs *TCP Server Mode*.
- The delimiter setting is optional: the bench setup ran without it as well. With it the device server forwards each answer of the master as one piece.
- A new Moxa NPort answers at `192.168.127.254`. To reach it, give your PC a temporary address in the `192.168.127.x` network or use Moxa's *Device Search Utility*, then change the network settings.
- Set a password on the device server and keep it on a trusted network: whoever reaches the TCP port can operate the installation.

### Working with INNOXEL Setup

Most serial device servers accept a single TCP connection, and Home Assistant holds it permanently. INNOXEL Setup therefore cannot reach the master while the integration is running.

Before you change the programming of the master with INNOXEL Setup:

1. Turn off the switch **Connection to the master** on the device page of the integration. Home Assistant releases the connection; all channels become unavailable.
2. Do your work in INNOXEL Setup and close its connection.
3. Turn the switch on again.

The switch is on after every restart of Home Assistant. Automations that send keys fail with an error while the connection is switched off.

## Polling

The master has no push channel. The integration reads the state of all outputs and dimmers every two seconds and the weather station every thirty seconds; after a key that Home Assistant sent, the state is read back within a fraction of a second. A change made at a wall button shows up after two seconds at the latest.

## Diagnostics

**Download diagnostics** in the entry's menu (⋮) under **Settings → Devices & services → Innoxel Master 2** gives one file with the firmware revision, the raw state and weather answers of the master exactly as they came over the serial line, your channels with their addresses, and the entities with their current state. The address of the serial device server is redacted; the names of your channels stay readable. Attach the file to a bug report — with the raw answers a dimmer value or a weather value can be checked without access to your installation.

## Removal

1. **Settings → Devices & services → Innoxel Master 2**, open the entry's menu (⋮) and choose **Delete**. The entities and their history go with the entry; the master itself is not changed.
2. Remove the integration itself in the **Marketplace** (or HACS), then restart Home Assistant. With a manual installation, delete `custom_components/innoxel_master2` instead.

## Quality scale

The integration declares **Bronze** on the [Home Assistant integration quality scale](https://developers.home-assistant.io/docs/core/integration-quality-scale/): a config flow with tests, unique ids for every entity, brand images, installation and removal instructions, a connection check before an entry is created, no duplicate entries, runtime data on the config entry, a documented action, and the other Bronze rules. The tier is self-assessed, as it is for every custom integration; the per-rule status, including what is still open for Silver and Gold, is in `custom_components/innoxel_master2/quality_scale.yaml`.

## Known limitations

- The master does not report channel names or its programming, so channels are added by hand.
- Outputs can only be operated through keys programmed in INNOXEL Setup, not directly.
- A dimmer cannot be set to a value, only operated with its key; the value range of `dim_value` is unverified.
- The position of a blind is unknown to the master.
- Key presses at wall buttons are not reported, only their effect on the outputs.
- One TCP connection per device server, see [Working with INNOXEL Setup](#working-with-innoxel-setup).

## Disclaimer

This integration is provided **as-is, without any warranty**. It controls real hardware — covers/blinds, lights, other loads. Use it at your own risk. The author(s) accept **no responsibility or liability** for any damage, malfunction, incorrect behavior, data loss, or other issues arising from using this integration, whether it stops working, behaves unexpectedly, or never worked correctly for your setup in the first place. Test thoroughly in your own environment before relying on it for anything safety- or property-relevant.

## License

Copyright (C) 2026 prusuino

Source code: GNU General Public License v3.0 (GPL-3.0) — see [LICENSE](LICENSE). You may use, change and share it; if you pass it on, changed or built into something else, that has to be under the same licence and with its source code. It comes without any warranty. Not affiliated with Innoxel.

## Related integrations

More Home Assistant integrations from the same author:

- [Innoxel Master 3](https://github.com/prusuino/ha_innoxel_master3) — native local control of the Innoxel Master 3 over its SOAP interface
- [RD30 Digital Interface](https://github.com/prusuino/ha_rd30) — 30 contact inputs of an AK MODUL-BUS RD30 over a serial device server
- [Swiss Waters](https://github.com/prusuino/ha_swiss_waters) — live water temperature, water level, discharge and flood danger levels of Swiss rivers and lakes
- [Swiss Charging Stations](https://github.com/prusuino/ha_swiss_charging_stations) — real-time availability and prices of public EV charging stations in Switzerland
- [Austrian Charging Stations](https://github.com/prusuino/ha_austrian_charging_stations) — real-time availability of public EV charging stations in Austria
- [Swiss Transport](https://github.com/prusuino/ha_swiss_transport) — live public-transport departure boards and saved connections
- [Swiss Parking](https://github.com/prusuino/ha_swiss_parking) — live free parking spaces in Swiss cities
- [Swiss Electricity Price](https://github.com/prusuino/ha_swiss_electricity_price) — electricity tariffs of any Swiss grid operator (ElCom)
- [Swiss Solar Reference Price](https://github.com/prusuino/ha_swiss_solar_reference_price) — the Swiss solar reference market price (SFOE)
- [Swiss Earthquakes](https://github.com/prusuino/ha_swiss_earthquakes) — recent Swiss earthquakes on the built-in map
- [Swiss Public Alerts](https://github.com/prusuino/ha_swiss_public_alerts) — official Swiss public alerts (Alertswiss) with home-location matching
- [Swiss Avalanche Bulletin](https://github.com/prusuino/ha_swiss_avalanche_bulletin) — the official SLF avalanche bulletin for your location
- [Swiss Hail Protection](https://github.com/prusuino/ha_swiss_hail_protection) — Swiss hail warnings for your blinds: the official VKF hail-protection signal or the MeteoSwiss hail radar around you
- [Swiss Lottery](https://github.com/prusuino/ha_swiss_lottery) — the latest Swiss Lotto, EuroMillions and EuroDreams draws from Swisslos, your tickets checked against every draw, with a dashboard card
- [Swiss Meteo](https://github.com/prusuino/ha_swiss_meteo) — MeteoSwiss open data: local forecast, live station values, official warnings, pollen, station history and dashboard cards
- [Swiss Solar Forecast](https://github.com/prusuino/ha_swiss_solar_forecast) — PV production forecast from the MeteoSwiss local forecast and the Sonnendach solar cadastre
- [Marstek Venus Surplus Control](https://github.com/prusuino/ha_venus_surplus_control) — runs a Marstek Venus battery from PV surplus, also next to an inverter battery
- [Swiss Shared Mobility](https://github.com/prusuino/ha_swiss_shared_mobility) — shared bikes, e-scooters and cars available near you in Switzerland

## Support

If this integration is useful to you, you can support its development:

<a href="https://www.buymeacoffee.com/prusuino"><img src="https://cdn.buymeacoffee.com/buttons/v2/default-yellow.png" alt="Buy Me A Coffee" height="41"></a>
