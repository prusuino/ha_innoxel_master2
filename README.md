# Innoxel Master 2 for Home Assistant

Custom integration for the **Innoxel Master 2** (NOXmaster) building automation
controller. The Master 2 has no network port; it is reached through a serial
device server such as a Moxa NPort 5110 in TCP server mode.

> Early development version. Tested on a bench with one Switch 8 module. Dimmer,
> blind and weather support follow the protocol but have not been verified on
> real hardware yet.

For the Innoxel Master 3 use
[ha_innoxel_master3](https://github.com/prusuino/ha_innoxel_master3) instead.

## What you need

- Innoxel Master 2 connected by RS-232 to a serial device server
- Device server in **TCP server mode**, 115200 baud, 8 data bits, no parity,
  1 stop bit, no flow control, delimiter `0D` (see the Innoxel guide for the
  Moxa NPort 5110)
- Keys programmed in INNOXEL Setup for everything Home Assistant should
  control. The integration operates the installation the way a wall button
  does: it presses keys and reads the state of the outputs back.

## How it works

| Channel type | What you enter | What you get |
|---|---|---|
| Switch | key, output (detected when left empty) | `switch` with real state |
| Light | key, output (detected when left empty) | `light` with real state |
| Dimmer | key, dimmer channel | on/off `light`, dim value as attribute |
| Blind | key up, key down, optionally the motor outputs | `cover` with open, close, stop |
| Key | key | `button`, e.g. for a scene |

Addresses use the Innoxel notation: outputs `O0-3`, inputs `I10-1`, dimmers
`D0-2`. For inputs the event number shown in INNOXEL Setup works as well
(`GR28` is `I10-1`).

A weather station connected to the master shows up automatically as sensors
(temperature, wind speed, sun east/south/west, twilight, rain).

The action `innoxel_master2.send_key` sends a key impulse, or press and
release separately for a long key press.

## Limitations

- The master is polled every two seconds; it cannot push changes.
- The master does not report channel names, so channels are added by hand.
- A dimmer cannot be set to a value, only operated with its key.
- The blind position is unknown to the master.
- Most device servers accept one TCP connection. While Home Assistant is
  connected, INNOXEL Setup cannot use the same device server, and vice versa.

## Disclaimer

This is a private project and not affiliated with INNOXEL System AG or
ZidaTech AG. Use at your own risk.
