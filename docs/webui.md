# First read-only WebUI

## Access and data

The systemd service simpleinventory-web.service listens on 0.0.0.0:80. Use the LXC IPv4 address or a DNS name resolving to it in a browser. A separate DNS record must be provided by your router or DNS server if desired.

GET / displays the configured inventory and its items. GET /api/inventory provides the same selected fields as JSON. Both read fresh data from HA. The application does not provide inventory write endpoints in this version. GET /health checks the web process, not HA connectivity.

On HA connection, authentication or inventory failure, the UI responds with a neutral message and HTTP 503. Tokens, HA addresses and upstream exception payloads are not exposed. HTML templates escape HA-provided content.

## Service and credentials

The service uses the dedicated simpleinventory-webui account, not root. Its only retained Linux capability is CAP_NET_BIND_SERVICE for port 80. Code is root-owned under /opt/simpleinventory-webui/releases, with current pointing at the deployed version.

systemd reads the root-only /etc/simpleinventory-webui/app.env and passes the HA settings to the web process. The service account does not need direct read access to that private file. Code installation never overwrites private settings. After manually changing HA configuration, restart the web service. The updated simpleinventory-setup helper does this after a successful configuration save.

The service is enabled at installation and restarts after a container reboot. Existing Proxmox onboot settings are unchanged; automatic container startup on host boot remains a separate Proxmox setting.

## Prepared shared-password mode

Default: password authentication is disabled. This means every client that can reach the port can read the inventory; it is not a firewall restriction.

A single-password login form is implemented with no username. Optional settings belong in /etc/simpleinventory-webui/web.env, root-owned with mode 0600. The settings are:
- SIW_AUTH_ENABLED: true to require configured authentication.
- SIW_LOCAL_BYPASS: true to bypass the password for directly connected private IPv4 subnets; false to require it for all clients.
- SIW_PASSWORD_HASH: PBKDF2-SHA256 in the format pbkdf2_sha256, 600000, a 16-byte random salt in hexadecimal and a SHA256 digest in hexadecimal, separated by dollar characters.
- SIW_SESSION_SECRET: a locally generated random secret of at least 32 characters for signed cookies.

Actual values must be generated locally and never committed. Restart simpleinventory-web.service after configuring them. Enabling authentication without valid private settings prevents service startup instead of silently disabling protection. A dedicated password-configuration helper and HTTPS deployment are future work; use HTTPS before sending passwords across untrusted networks.

The login uses signed expiring cookies, CSRF checks, bounded input and an in-memory attempt limit. It is not a multi-user system.

## Local subnet recognition

A private-looking client IP alone does not make a client local. The application reads active interface addresses and their real prefix lengths. Only directly connected IPv4 subnets fully inside RFC1918 ranges are eligible. Networks are refreshed every 30 seconds; discovery failure grants no bypass.

Thus an address with /23 uses that actual /23, not an assumed /24. The logic works with DHCP in different private networks without hardcoding one LAN. Loopback is also allowed when local bypass is enabled. IPv6 bypass is not implemented.

The server explicitly ignores forwarded HTTP headers and does not use X-Forwarded-For for authorization. A reverse proxy would require a separate trust design before being used with local bypass.

## Validation

22 automated tests passed in the Debian 13 test LXC, covering the HA setup and WebUI, including HTML escaping, empty inventories, upstream failure handling, optional password sessions, CSRF checks, login size/attempt limits, local-subnet changes and spoofed forwarding headers.

The real configured HA inventory was displayed successfully after deployment. The service runs as its dedicated non-root user and the private HA configuration file was verified unchanged. The existing v0.1.0 snapshot remains the recovery baseline.
