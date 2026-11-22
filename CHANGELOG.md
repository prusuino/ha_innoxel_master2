# Changelog

## 1.2.0 — 2026-11-22

- **New channel type: sensor.** *Add sensor* takes an output address and gives a `binary_sensor` with the state of that output, without a key. It is meant for what the master reports among the outputs but Home Assistant should not operate: a 230 V input module (NOXin-0800h, which is addressed like an output) or an output the master uses as a flag, such as the night setback or the release of a weather function.
- **Faster.** The state of the outputs and dimmers is read every second instead of every two, so a change at a wall button shows up within a second. After a command from Home Assistant the new state is read at once instead of after a fixed pause of 0.3 seconds; the master confirms a key only when it has carried it out. Measured on a Master 2 (REV 09.23) through a Moxa NPort: one state poll takes about 45 ms, and the new state is in Home Assistant about 0.1 seconds after the key.
- The README names the firmware the interface needs (9.00 or newer, according to Innoxel's documentation of its remote control).

## 1.1.0 — 2026-11-22

- **Diagnostics download.** The entry's menu under *Settings → Devices & services* offers *Download diagnostics*: the firmware revision, the raw state and weather answers of the master, the channels with their addresses and the entities with their current state. The address of the serial device server is redacted. The bug report form asks for the file.

## 1.0.0 — 2026-11-22

- **French and Italian.** The dialogs, entity names, the action and its error messages are translated into French and Italian, next to German and English.
- **Documentation.** The README follows the structure of the Innoxel Master 3 integration and describes how the serial device server has to be set up (serial settings and operating mode of a Moxa NPort 5110), how blinds behave, how often the master is read and how INNOXEL Setup stays usable.
- **Tests.** The serial protocol, the setup dialog, the channel dialogs, the entities, the connection switch and the action are tested against a stand-in master; a workflow runs the tests on every change.
- **Quality scale: Bronze**, self-assessed; the per-rule status is in `quality_scale.yaml`.
- **Release file.** A release now carries `innoxel_master2.zip`, which HACS and the Home Assistant Marketplace download.
- The Home Assistant Marketplace lists the integration under *Hubs & protocols → Building automation*, *Blinds & curtains* and *Lighting*.
- Nothing changes in how the integration works compared with 0.1.0.

## 0.1.0 — 2026-11-22

First public version.

- Setup by the address and TCP port of the serial device server; the master is asked for its firmware revision.
- Channels are added one by one: switch, light, dimmer, blind and key. A switch or light finds its output by itself when the address is left empty.
- Switches and lights show the state the master reports and press their key only when the output is in the other state.
- Blinds run with a key impulse and stop with an impulse in the running direction.
- Weather station: temperature, wind speed, sun east/south/west, twilight and rain, when a weather station is connected.
- Action `innoxel_master2.send_key` for an impulse or a separate press and release.
- Switch **Connection to the master** releases the device server for INNOXEL Setup.
- German and English.
