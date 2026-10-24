# SimpleInventory-WebUI

A planned Python web interface for the Simple Inventory integration in Home Assistant.

## Current state

This repository currently contains the installation foundation and credential policy, not a working WebUI. Existing LICENSE is retained. No Home Assistant instance has been configured, and no LXC is created by this installer.

## Intended architecture

Browser -> Python FastAPI application -> authenticated Home Assistant WebSocket API -> Simple Inventory.
Home Assistant remains the source of truth; no separate inventory database is required. The application depends on HA being available.

- FastAPI: routes, input validation and application logic.
- Uvicorn: HTTP server.
- Jinja2 plus local HTML/CSS and minimal JavaScript: responsive user interface; no Node.js build service required.
- websockets: Home Assistant connection, authentication, request IDs, reconnection and event subscriptions.
- httpx: HTTP calls if needed.
- pydantic-settings: configuration from manually supplied runtime settings.
- python-multipart: HTML form handling.
- itsdangerous: signed session support; complete authentication and CSRF handling still need implementation.
- systemd (provided by the Debian container): eventual service startup and restart.

Initial UI scope: list inventories; search/filter items by category and location; create/edit items; increment/decrement quantities; confirm deletion; display successful or failed saves. The backend must reconcile uncertain write results instead of blindly retrying.

## One-command Proxmox installation

Run as root in the **Proxmox host shell**:

```bash
bash -c "$(curl -fsSL https://raw.githubusercontent.com/VexMex/SimpleInventory-WebUI/main/install.sh)"
```

The host needs curl, normally available on Proxmox. Review install.sh before running it. A download failure must not be mistaken for success: a setup banner and prompts must appear. The short launcher follows the Community Scripts invocation style.

The installer asks for container ID, hostname, disk storage, template storage, bridge, CPU, memory and disk size, then asks for confirmation. Enter accepts the suggested value. Defaults: a free ID, Debian 13 amd64, unprivileged, 1 core, 1 GB RAM, 4 GB disk, DHCP. Nesting is enabled for systemd 257 compatibility. No GPU or Docker is required. Automatic startup on host boot is disabled for this development foundation.

It downloads the Debian template when needed, creates a NEW LXC, starts it and installs Python dependencies. Existing guests are never reused or deleted. On failure a new guest is retained for diagnosis. Cancelling creates no guest.

The guest bootstrap is pinned to a reviewed revision and SHA-256 checksum. The entry script on main can change; Python dependencies still use development ranges. A production release requires full dependency locking.

For automated tests, SIW_NONINTERACTIVE=1 skips prompts. SIW_CTID, SIW_HOSTNAME, SIW_STORAGE, SIW_TEMPLATE_STORAGE, SIW_BRIDGE, SIW_CORES, SIW_MEMORY and SIW_DISK override defaults. Existing IDs are rejected. Credentials are never installer arguments.

**Current result:** a prepared Python environment and a manual HA setup command, not a running WebUI. No HA token is requested by the installer. After creation, run `/usr/local/bin/simpleinventory-setup` inside the LXC; see [HA setup](docs/ha-setup.md). The host installer is self-contained; it follows the host/guest split without sourcing changing Community Scripts helper libraries.

See [guest bootstrap test](docs/bootstrap-test.md).

## Credentials

Read SECURITY.md and AGENTS.md before changing or uploading anything. Real credentials never belong on GitHub. The user permits local runtime storage in the installation LXC: /etc/simpleinventory-webui/app.env, outside the source tree, owned by root with mode 0600. Manual HA token configuration and a boot-time connection check are implemented; the application login and WebUI still need implementation.

References:
- https://github.com/blaineventurine/simple_inventory
- https://github.com/community-scripts/ProxmoxVE/blob/main/ct/homebox.sh
- https://github.com/community-scripts/ProxmoxVE/blob/main/install/homebox-install.sh
- https://fastapi.tiangolo.com/
