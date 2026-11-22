# Security Policy

## Supported Versions

Only the latest release receives security fixes. Please update to the most
recent version before reporting an issue.

| Version | Supported |
| ------- | --------- |
| latest release | ✅ |
| older releases | ❌ |

## Reporting a Vulnerability

Please **do not** open a public GitHub issue for security vulnerabilities.

Instead, use GitHub's private vulnerability reporting: go to the
[Security tab](https://github.com/prusuino/ha_innoxel_master2/security) of this
repository and click **"Report a vulnerability"**. You will get a response
within a few days. Once a fix is available, the vulnerability will be
disclosed in the release notes.

## Security Considerations

This integration communicates exclusively with a serial device server on your
**local network**, which passes the data on to the RS-232 port of the Innoxel
Master 2 — no cloud services are involved and no data leaves your network.

Things worth knowing:

- The serial protocol of the Master 2 has **no login and no encryption**.
  Whoever can open the TCP port of the serial device server can read the
  state of the installation and press its keys. Run the device server on a
  trusted network.
- The integration stores only the address and the TCP port of the device
  server and the channels you add; there are no credentials.
- Set a password on the configuration interface of the serial device server,
  so that its settings cannot be changed by anyone on the network.
- **Never expose the TCP port of the serial device server to the internet.**
  If you need remote access, use a VPN or Home Assistant's own remote access
  mechanisms.
